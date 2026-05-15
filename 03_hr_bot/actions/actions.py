"""Custom actions HR-бота.

Скелет: классы-заглушки, объявленные в `domain.yml`, чтобы `rasa train`
не ругалась на undefined actions. Реальная логика добавляется по промптам:

- `ActionResetInterview`        → Промпт 7 (sad-paths, restart-flow)
- `ValidateInterviewForm`       → Промпт 4 (имя/email) → Промпты 5–6 (остальные слоты)
- `ActionAssessCandidate`       → Промпт 6 (assessment engine + CSV)
- `ActionOfferAlternativeRole`  → Промпт 6 (альтернативная роль)

Стиль соответствует `02_phones_bot/actions/actions.py`: type hints, logging,
docstring на каждый класс.
"""

import csv
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import ActiveLoop, AllSlotsReset, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction

logger = logging.getLogger(__name__)

# Промпт 7: путь до CSV с требованиями по 5 ролям (см. roles_requirements.csv).
# Шаблон тот же, что в 02_phones_bot: путь относительно текущего файла, чтобы
# работало и из `rasa run actions`, и при импорте из тестов.
# В отличие от phones_bot, тут НЕ используем pandas — pandas не в зависимостях
# .venv, и таблица крошечная (5 строк), stdlib `csv` достаточно.
ROLES_CSV = Path(__file__).parent.parent / "roles_requirements.csv"

# Промпт 4: regex для валидации email. Компилируем один раз на модуль, чтобы
# не платить за пересборку при каждом вызове validate_candidate_email.
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Промпт 5: regex выдёргивания первого числа из строки (поддерживает «5», «3.5»,
# «3,5», «3 года»). Используется в validate_years_experience при from_text-вводе.
YEARS_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

# Промпт 6: regex для leading-числа в строке зарплаты (после удаления валюты и
# сжатия пробелов внутри числа). Поддерживает целые и дробные значения.
SALARY_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

# Промпт 6: regex-маркеры суффиксов «тысячи». Хвост у слова «тыс/тысяч/тысячи»
# может быть с любыми гласными окончаниями — матчим всё семейство.
_SALARY_THOUSANDS_RE = re.compile(r"тыс(?:яч[аи]?)?")
# Узкий неразрывный пробел (U+202F) и обычный неразрывный пробел (U+00A0) —
# часто встречаются в скопированных значениях вида «150 000 ₽».
_SALARY_THIN_SPACES = (" ", " ")
# Слова валюты, которые мы вырезаем перед парсингом числа. Порядок имеет значение:
# «рублей»/«руб.» матчатся раньше короткого «руб», иначе останется «лей»/«.».
_SALARY_CURRENCY_TOKENS = ("рублей", "руб.", "руб", "₽", " р")


def _parse_salary(text: str) -> "float | None":
    """Парсит зарплатный ввод в число рублей.

    Поддерживаемые форматы (после lowercasing и нормализации пробелов/валюты):
      • «150000», «150 000», «150_000» → 150000.0
      • «150к», «150 к», «150k» → 150000.0
      • «150 тысяч», «150 тыс», «200 тысячи» → 150000.0 / 200000.0
      • «150 000 ₽», «300 000 руб», «200к рублей» → 150000.0 / 300000.0 / 200000.0

    Возвращает float или None, если строка не содержит распознаваемого числа.

    >>> _parse_salary("150000")
    150000.0
    >>> _parse_salary("150 000 ₽")
    150000.0
    >>> _parse_salary("200к")
    200000.0
    >>> _parse_salary("180 тысяч")
    180000.0
    >>> _parse_salary("много") is None
    True
    >>> _parse_salary("") is None
    True
    >>> _parse_salary("abc xyz") is None
    True
    >>> _parse_salary("   ") is None
    True
    >>> _parse_salary("300 000 руб")
    300000.0
    >>> _parse_salary("200к рублей")
    200000.0
    """
    if text is None:
        return None
    s = str(text).lower().strip()
    if not s:
        return None

    # Нормализуем неразрывные/тонкие пробелы к обычным.
    for ch in _SALARY_THIN_SPACES:
        s = s.replace(ch, " ")

    # Срезаем валютные суффиксы. Список упорядочен от длинных к коротким, чтобы
    # «рублей» матчилось раньше «руб» и не оставляло «лей».
    for token in _SALARY_CURRENCY_TOKENS:
        s = s.replace(token, " ")

    # Определяем множитель: «к»/«k»/«тыс*» → 1000, иначе 1.
    multiplier = 1
    if _SALARY_THOUSANDS_RE.search(s):
        multiplier = 1000
        s = _SALARY_THOUSANDS_RE.sub(" ", s)
    elif "к" in s or "k" in s:
        multiplier = 1000
        s = s.replace("к", " ").replace("k", " ")

    # Сжимаем пробелы и подчёркивания внутри числа: «150 000» → «150000».
    s = s.replace("_", "")
    s = re.sub(r"(?<=\d)[\s](?=\d)", "", s)

    match = SALARY_NUMBER_RE.search(s)
    if match is None:
        return None
    try:
        value = float(match.group(0).replace(",", "."))
    except ValueError:
        return None

    return value * multiplier


def _normalize_skills(values: List[str]) -> List[str]:
    """Нормализует список навыков: распаковывает, lower, strip, дедуп.

    DIET кладёт в list-слот несколько entity-значений; каждое — строка. На случай
    случайной вложенности (одно значение — список) распаковываем один уровень.
    Регистр приводим к lower-case (валидатор ниже сравнивает с lookup-словарём
    кейс-инсенситивно), пустые строки убираем, дубликаты — preserving order.
    """
    flat: List[str] = []
    for v in values or []:
        if isinstance(v, list):
            flat.extend(str(x) for x in v)
        else:
            flat.append(str(v))

    seen: set[str] = set()
    result: List[str] = []
    for raw in flat:
        cleaned = raw.strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


@lru_cache(maxsize=1)
def _load_roles() -> Dict[str, Dict[str, str]]:
    """Загружает roles_requirements.csv в dict[role_code] -> row dict.

    Кэширована через `lru_cache` — действиям не нужно перечитывать файл при
    каждом запросе (он не меняется между перезапусками action-server).
    Пустые ячейки (`alternative_role` для PM, `required_skills` для PM)
    остаются пустыми строками — `_split_skills` обрабатывает корректно.
    """
    roles: Dict[str, Dict[str, str]] = {}
    with ROLES_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # csv.DictReader не превращает «» в None — пустая строка как есть.
            roles[row["role"]] = {k: (v or "") for k, v in row.items()}
    return roles


def _split_skills(raw: str) -> set:
    """Парсит CSV-строку `python;sql;...` в множество lower-case навыков.

    Пустая строка даёт пустое множество — это валидно (например, PM
    не имеет required_skills и считается «навыками подходит» автоматически).
    """
    if not raw:
        return set()
    return {s.strip().lower() for s in str(raw).split(";") if s.strip()}


def _role_row(roles: Dict[str, Dict[str, str]], role_code: str) -> Optional[Dict[str, str]]:
    """Возвращает строку CSV для канонического кода роли (pm/da/de/ds/mlops)."""
    if not role_code:
        return None
    return roles.get(role_code)


def _run_assessment(
    dispatcher: CollectingDispatcher,
    tracker: Tracker,
    *,
    desired_role: str,
) -> List[Dict[Text, Any]]:
    """Общая логика оценки кандидата — вызывается из обоих action'ов.

    Возвращает список events (включая SlotSet("assessment_decision", ...)) и
    диспатчит ответы пользователю. Не использует FollowupAction — чтобы не
    плодить вторичные предсказания политик и не упираться в circuit breaker.
    """
    candidate_name = tracker.get_slot("candidate_name") or "кандидат"
    years_experience = tracker.get_slot("years_experience")
    skills = tracker.get_slot("skills") or []
    expected_salary = tracker.get_slot("expected_salary")

    try:
        roles = _load_roles()
    except FileNotFoundError:
        logger.error("roles_requirements.csv не найден: %s", ROLES_CSV)
        dispatcher.utter_message(
            text="Внутренняя ошибка: база требований по ролям не найдена."
        )
        return [SlotSet("assessment_decision", "fail")]

    row = _role_row(roles, desired_role)
    if row is None:
        logger.error("Роль %r отсутствует в CSV", desired_role)
        dispatcher.utter_message(
            text=f"Внутренняя ошибка: роль {desired_role} не найдена в базе."
        )
        return [SlotSet("assessment_decision", "fail")]

    required = _split_skills(row["required_skills"])
    candidate_skills = {str(s).strip().lower() for s in skills}

    # Нормализуем числовые типы — слоты могут быть int/float/str (defensive).
    try:
        years_value = float(years_experience) if years_experience is not None else 0.0
    except (TypeError, ValueError):
        years_value = 0.0
    try:
        salary_value = float(expected_salary) if expected_salary is not None else 0.0
    except (TypeError, ValueError):
        salary_value = 0.0

    min_years = float(row["min_years"])
    salary_max = float(row["salary_max"])

    match_required = required.issubset(candidate_skills) if required else True
    match_years = years_value >= min_years
    over_salary = salary_value > salary_max

    logger.info(
        "assess result: role=%s required=%s candidate=%s match_required=%s match_years=%s over_salary=%s",
        desired_role, required, candidate_skills, match_required, match_years, over_salary,
    )

    events: List[Dict[Text, Any]] = []

    if match_required and match_years:
        decision = "pass"
        # Передаём kwargs явно: при цепном переходе (alternative→affirm) слот
        # desired_role в треккере ещё не обновлён (SlotSet попадает в events,
        # которые применятся после), поэтому полагаться на placeholder нельзя.
        dispatcher.utter_message(
            response="utter_assessment_pass",
            candidate_name=candidate_name,
            desired_role=desired_role,
        )
        if over_salary:
            dispatcher.utter_message(
                text=f"Учти, бюджет роли — до {salary_max:.0f} ₽."
            )
    elif match_years and not match_required:
        decision = "alternative"
        alt_code = (row["alternative_role"] or "").strip()
        alt_row = _role_row(roles, alt_code) if alt_code else None
        if alt_row is None:
            # Нет альтернативы → откатываем в fail (как в DESIGN.md §7.2).
            decision = "fail"
            missing = sorted(required - candidate_skills)
            dispatcher.utter_message(response="utter_assessment_fail_intro")
            dispatcher.utter_message(
                text=(
                    f"Не хватает обязательных навыков: {', '.join(missing)}."
                    if missing else "Не хватает обязательных навыков."
                )
            )
        else:
            alt_name = str(alt_row["role_name"])
            events.append(SlotSet("alternative_role_name", alt_name))
            # desired_role передаём явным kwarg'ом: при цепочке alt→alt (DS→DA→PM)
            # тут лежит уже НОВАЯ роль (kwarg-аргумент функции), а tracker.get_slot
            # ещё держит исходную «ds» — pending SlotSet применяется после run().
            # Без явного аргумента шаблон бы рендерил «По исходной роли ds» вместо
            # «da», обманывая пользователя про роль, на которую он только что
            # согласился.
            dispatcher.utter_message(
                response="utter_assessment_alternative_intro",
                desired_role=desired_role,
                alternative_role_name=alt_name,
            )
            missing = sorted(required - candidate_skills)
            if missing:
                dispatcher.utter_message(
                    text=f"Не хватает обязательных навыков: {', '.join(missing)}."
                )
            dispatcher.utter_message(
                response="utter_ask_accept_alternative",
                alternative_role_name=alt_name,
            )
    else:
        decision = "fail"
        dispatcher.utter_message(response="utter_assessment_fail_intro")
        dispatcher.utter_message(
            text=f"Нужно ≥ {min_years:.0f} лет опыта; у тебя {years_value:.0f}."
        )

    events.append(SlotSet("assessment_decision", decision))
    logger.info("assess: decision=%s", decision)
    return events


class ActionResetInterview(Action):
    """Сбрасывает состояние интервью.

    Промпт 8: реализация — диспатчит подтверждение
    `utter_restart_acknowledged` и возвращает события `AllSlotsReset()` +
    `ActiveLoop(None)`. `AllSlotsReset` обнуляет все слоты (вместо
    explicit `SlotSet(<name>, None)` для каждого — стандартная идиома RASA,
    не зависит от текущего списка слотов в domain). `ActiveLoop(None)`
    деактивирует `interview_form`, если он был активен.

    Срабатывает по двум rule'ам (см. `data/rules.yml`):
      • вне формы (`Перезапуск интервью вне формы`);
      • внутри активной формы (`Перезапуск интервью внутри активной формы`).
    """

    def name(self) -> Text:
        return "action_reset_interview"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        logger.info(
            "action_reset_interview: resetting all slots and deactivating form "
            "(active_loop=%r)",
            tracker.active_loop_name,
        )
        dispatcher.utter_message(response="utter_restart_acknowledged")
        return [AllSlotsReset(), ActiveLoop(None)]


class ActionTelegramStart(Action):
    """Реакция на команду `/start` (Telegram системная кнопка или ручной ввод).

    Промпт 9: Telegram присылает «/start» при первом контакте с ботом и при
    нажатии системной кнопки «Start» в шапке чата (в т.ч. сразу после очистки
    истории клиентом). Без специальной обработки бот оставался в прошлом
    состоянии (например, повторял результат assessment'а), потому что сервер
    про очистку истории на клиенте ничего не знает — tracker по chat_id живёт
    своей жизнью.

    Принципиально НЕ используем `Restarted()` через `action_restart`: этот
    event обнуляет весь tracker и обрывает текущее предсказание политики, из-за
    чего следующий шаг rule (`utter_greet`) до пользователя не доходит. Вместо
    этого диспатчим приветствие и возвращаем `AllSlotsReset` + `ActiveLoop(None)`
    — слоты и активная форма обнуляются, события трекера сохраняются, и
    политика продолжает предсказывать как обычно.
    """

    def name(self) -> Text:
        return "action_telegram_start"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        logger.info(
            "action_telegram_start: /start received, resetting slots "
            "(active_loop=%r)",
            tracker.active_loop_name,
        )
        dispatcher.utter_message(response="utter_greet")
        return [AllSlotsReset(), ActiveLoop(None)]


class ActionAssessCandidate(Action):
    """Оценивает кандидата по `roles_requirements.csv`.

    Алгоритм (DESIGN.md §7.2, уточнённый в Промпте 7):

    1. Загружает CSV. Если строки под `desired_role` нет — внутренняя ошибка
       (логируем + диспатчим пользователю; ставим decision=fail и выходим).
    2. Считает три флага:
       - `match_required` — все обязательные навыки из CSV есть у кандидата
         (пустой required → считаем True, как у PM).
       - `match_years` — `years_experience >= min_years`.
       - `over_salary` — `expected_salary > salary_max` (warning, не fail).
    3. Решение:
       - pass: match_required AND match_years.
       - alternative: match_years, но недостаёт required_skills.
       - fail: иначе (НЕ хватает опыта — это override; даже если навыки есть,
         мы не выпускаем кандидата с недостаточным стажем на альтернативу).
    4. Диспатчит:
       - pass → utter_assessment_pass; если over_salary — отдельным сообщением
         предупреждение про потолок бюджета.
       - fail → utter_assessment_fail_intro + текст с указанием требуемых лет.
       - alternative → utter_assessment_alternative_intro
         (со слотами desired_role + alternative_role_name) + список
         недостающих навыков + utter_ask_accept_alternative (кнопки Да/Нет).
    5. Возвращает SlotSet("assessment_decision", decision) и при alternative
       — SlotSet("alternative_role_name", <человекочитаемое имя>) для шаблонов.
    """

    def name(self) -> Text:
        return "action_assess_candidate"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        desired_role = tracker.get_slot("desired_role")
        candidate_email = tracker.get_slot("candidate_email")
        logger.info("assess called: role=%r email=%r", desired_role, candidate_email)
        return _run_assessment(dispatcher, tracker, desired_role=desired_role)


class ActionOfferAlternativeRole(Action):
    """Перезапускает оценку под альтернативную роль.

    Триггерится rule «Согласие на альтернативу» (assessment_decision=alternative
    + intent affirm). Логика:

    1. Берёт текущий desired_role, ищет alternative_role в CSV.
    2. Если пусто или нет в базе — извиняется и сбрасывает решение в fail.
    3. Иначе: переустанавливает desired_role на код альтернативы и
       сразу же вызывает `_run_assessment(...)` для новой роли — не через
       FollowupAction, чтобы не плодить лишние предсказания политик
       (после FollowupAction RulePolicy уходила в core_fallback и
       тригерила circuit breaker).

    Остальные слоты формы (имя, email, опыт, навыки, зарплата) намеренно
    оставляем — кандидат тот же, переоцениваем те же данные по новой роли.
    """

    def name(self) -> Text:
        return "action_offer_alternative_role"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        desired_role = tracker.get_slot("desired_role")
        try:
            roles = _load_roles()
        except FileNotFoundError:
            logger.error("roles_requirements.csv не найден: %s", ROLES_CSV)
            dispatcher.utter_message(
                text="Внутренняя ошибка: база требований по ролям не найдена."
            )
            return []

        row = _role_row(roles, desired_role)
        if row is None:
            logger.error("offer_alt: текущая роль %r отсутствует в CSV", desired_role)
            dispatcher.utter_message(text="Подходящих альтернатив нет, к сожалению.")
            return [SlotSet("assessment_decision", "fail")]

        alt_code = (row["alternative_role"] or "").strip()
        if not alt_code:
            dispatcher.utter_message(text="Подходящих альтернатив нет, к сожалению.")
            return [SlotSet("assessment_decision", "fail")]

        alt_row = _role_row(roles, alt_code)
        if alt_row is None:
            logger.error("offer_alt: альтернатива %r отсутствует в CSV", alt_code)
            dispatcher.utter_message(text="Подходящих альтернатив нет, к сожалению.")
            return [SlotSet("assessment_decision", "fail")]

        alt_name = str(alt_row["role_name"])
        dispatcher.utter_message(
            text=f"Хорошо, теперь рассматриваем тебя как {alt_name}."
        )

        # Сразу же оцениваем кандидата по новой роли, чтобы не дожидаться
        # отдельного FollowupAction (он провоцирует core_fallback после
        # завершения). Передаём alt_code напрямую вместо чтения слота.
        events: List[Dict[Text, Any]] = [
            SlotSet("desired_role", alt_code),
            SlotSet("alternative_role_name", alt_name),
        ]
        events.extend(_run_assessment(dispatcher, tracker, desired_role=alt_code))
        return events


class ValidateInterviewForm(FormValidationAction):
    """Per-slot валидация `interview_form`.

    Промпт 4: подключены валидаторы для `candidate_name` (минимум 2 токена —
    имя + фамилия) и `candidate_email` (regex `^...@...\\..{2,}$`). Остальные
    слоты (`years_experience`, `skills`, `expected_salary`) будут добавлены
    в Промптах 5–6 (см. DESIGN.md §7.1).
    """

    def name(self) -> Text:
        return "validate_interview_form"

    def validate_candidate_name(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Принимает имя, если в строке хотя бы два непустых токена.

        DIET тренируется на небольшом числе аннотаций `[Имя Фамилия](full_name)`
        и для редких имён (Фёдор, Пётр) выдёргивает только фамилию — слот через
        from_entity заполняется одним токеном и валидатор бесконечно
        переспрашивает. Поэтому, если entity-извлечение дало < 2 токенов,
        пробуем raw-text последнего сообщения (та же логика, что и при
        отсутствии full_name-entity — там сработал бы from_text-маппинг).

        Возвращает {"candidate_name": None} при отказе — форма переспросит
        тот же слот, и пользователь введёт значение заново.
        """
        candidates: List[str] = []
        if isinstance(slot_value, str) and slot_value.strip():
            candidates.append(slot_value)
        raw_text = (tracker.latest_message or {}).get("text") or ""
        if isinstance(raw_text, str) and raw_text.strip():
            # Только если не дублирует slot_value — иначе повторно прогоним то же.
            if not candidates or raw_text.strip() != candidates[0].strip():
                candidates.append(raw_text)

        for candidate in candidates:
            tokens = [t for t in candidate.strip().split() if t]
            if len(tokens) >= 2:
                cleaned = " ".join(tokens)
                logger.debug(
                    "validate_candidate_name: accepted %r (source=%s)",
                    cleaned,
                    "entity" if candidate is slot_value else "raw_text",
                )
                return {"candidate_name": cleaned}

        logger.debug(
            "validate_candidate_name: no ≥2-token candidate (slot=%r, text=%r)",
            slot_value, raw_text,
        )
        dispatcher.utter_message(response="utter_invalid_name")
        return {"candidate_name": None}

    def validate_candidate_email(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Принимает email, если он матчит EMAIL_RE; нормализует к lower-case."""
        if not slot_value or not isinstance(slot_value, str):
            logger.debug("validate_candidate_email: empty value, asking again")
            return {"candidate_email": None}

        candidate = slot_value.strip()
        if not EMAIL_RE.match(candidate):
            logger.debug("validate_candidate_email: bad format %r", candidate)
            dispatcher.utter_message(response="utter_invalid_email")
            return {"candidate_email": None}

        normalized = candidate.lower()
        logger.debug("validate_candidate_email: accepted %r", normalized)
        return {"candidate_email": normalized}

    def validate_years_experience(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Принимает число лет опыта (0–50). Парсит «5», «3 года», «3.5», «3,5».

        Если entity-extractor вернул чистое число — приходит float/int.
        Если from_text — приходит строка, из неё выдёргивается первое число
        (запятая → точка, чтобы float() не падал на «3,5»).
        """
        if slot_value is None or slot_value == "":
            logger.debug("validate_years_experience: empty value, asking again")
            return {"years_experience": None}

        # Числовой тип — берём как есть; строковый — парсим первое число.
        if isinstance(slot_value, (int, float)):
            parsed: float | None = float(slot_value)
        else:
            match = YEARS_NUMBER_RE.search(str(slot_value))
            if match is None:
                parsed = None
            else:
                try:
                    parsed = float(match.group(0).replace(",", "."))
                except ValueError:
                    parsed = None

        if parsed is None or parsed < 0 or parsed > 50:
            logger.debug("validate_years_experience: invalid %r", slot_value)
            dispatcher.utter_message(response="utter_invalid_experience")
            return {"years_experience": None}

        logger.debug("validate_years_experience: accepted %r", parsed)
        return {"years_experience": parsed}

    def validate_skills(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Нормализует список навыков и отвергает пустой ввод.

        DIET для list-слотов передаёт уже список строк (несколько entity-вхождений
        склеиваются автоматически). На случай одиночного entity / from_text
        (если позже добавим) — приводим к списку и нормализуем через
        `_normalize_skills`.
        """
        if slot_value is None:
            values: List[str] = []
        elif isinstance(slot_value, list):
            values = slot_value
        else:
            values = [slot_value]

        normalized = _normalize_skills(values)

        if not normalized:
            logger.debug("validate_skills: empty after normalization (%r)", slot_value)
            dispatcher.utter_message(response="utter_invalid_skills")
            return {"skills": None}

        logger.debug("validate_skills: accepted %r", normalized)
        return {"skills": normalized}

    def validate_expected_salary(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Принимает зарплату в диапазоне 50 000–1 500 000 ₽.

        Делегирует парсинг в `_parse_salary` (умеет «150000», «150 000»,
        «150к», «150 тысяч», «300 000 руб» и т.п.). При неуспехе или выходе
        за диапазон диспатчит `utter_invalid_salary` и возвращает None —
        форма переспросит тот же слот.
        """
        if slot_value is None or slot_value == "":
            logger.debug("validate_expected_salary: empty value, asking again")
            return {"expected_salary": None}

        parsed = _parse_salary(str(slot_value))
        if parsed is None or parsed < 50000 or parsed > 1500000:
            logger.debug("validate_expected_salary: invalid %r (parsed=%r)", slot_value, parsed)
            dispatcher.utter_message(response="utter_invalid_salary")
            return {"expected_salary": None}

        logger.debug("validate_expected_salary: accepted %r", parsed)
        return {"expected_salary": parsed}
