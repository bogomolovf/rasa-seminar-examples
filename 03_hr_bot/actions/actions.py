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

import logging
import re
from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction

logger = logging.getLogger(__name__)

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


class ActionResetInterview(Action):
    """Сбрасывает состояние интервью.

    На Промпте 2 — пустая заглушка. В Промпте 7 будет возвращать SlotSet(None)
    для всех слотов, ActiveLoop(None) и FollowupAction("utter_restart_done").
    """

    def name(self) -> Text:
        return "action_reset_interview"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        logger.debug("action_reset_interview: skeleton run (no-op)")
        return []


class ActionAssessCandidate(Action):
    """Оценивает кандидата по `roles_requirements.csv`.

    На Промпте 2 — пустая заглушка. В Промпте 6 будет:
    - читать CSV через pandas,
    - сравнивать слоты `years_experience`, `skills`, `expected_salary`
      с требованиями для `desired_role`,
    - выставлять `assessment_decision` ∈ {pass, fail, alternative}.
    """

    def name(self) -> Text:
        return "action_assess_candidate"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        logger.debug("action_assess_candidate: skeleton run (no-op)")
        return []


class ActionOfferAlternativeRole(Action):
    """Предлагает альтернативную роль, если основная не подошла.

    На Промпте 2 — пустая заглушка. В Промпте 6 возьмёт `alternative_role`
    из CSV и при `affirm` перезапустит оценку на новой роли.
    """

    def name(self) -> Text:
        return "action_offer_alternative_role"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        logger.debug("action_offer_alternative_role: skeleton run (no-op)")
        return []


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

        Возвращает {"candidate_name": None} при отказе — форма переспросит
        тот же слот, и пользователь введёт значение заново.
        """
        if not slot_value or not isinstance(slot_value, str):
            logger.debug("validate_candidate_name: empty value, asking again")
            return {"candidate_name": None}

        tokens = [t for t in slot_value.strip().split() if t]
        if len(tokens) < 2:
            logger.debug("validate_candidate_name: only one token %r", slot_value)
            dispatcher.utter_message(response="utter_invalid_name")
            return {"candidate_name": None}

        cleaned = " ".join(tokens)
        logger.debug("validate_candidate_name: accepted %r", cleaned)
        return {"candidate_name": cleaned}

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
