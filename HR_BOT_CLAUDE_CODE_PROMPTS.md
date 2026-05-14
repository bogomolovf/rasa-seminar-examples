# HR-бот на RASA — пошаговые промпты для Claude Code

Этот файл содержит **последовательность промптов**, которые нужно по одному вставлять в Claude Code в корне репозитория `examples/`. Каждый промпт самодостаточен: содержит контекст, цель, ограничения, критерии готовности и шаги по коммиту/пушу.

## Что мы строим

`examples/03_hr_bot/` — RASA-бот для **скрининга кандидатов** на одну из 5 ролей ML-команды:

1. **Project Manager** (PM)
2. **Data Analyst** (DA)
3. **Data Engineer** (DE)
4. **Data Scientist** (DS)
5. **MLOps Engineer** (MLOps)

Бот собирает: имя, email, желаемую роль, опыт (годы), навыки, ожидаемую зарплату. Сравнивает с требованиями роли. Выдаёт решение: **pass / fail / alternative** (предложить смежную роль).

Базовая архитектура — как в `02_phones_bot` (formы, slot filling, custom action, CSV-база), но логика принятия решения сложнее.

## Как пользоваться этим файлом

1. Откройте Claude Code в корне репозитория `examples/`.
2. Берите блоки **Промпт N** по порядку, вставляйте по одному.
3. Дождитесь, пока Claude закончит и сделает коммит/пуш, прежде чем брать следующий.
4. Если что-то пошло не так — в конце каждого промпта есть «возврат к чистому состоянию», используйте `/clear` и повторите промпт.

> Промпты намеренно длинные. Это не баг — это явный контекст, который заменяет рутинные уточняющие вопросы и не даёт Claude уйти в импровизацию.

---

## Промпт 0 — однократная настройка инфраструктуры

```text
Сделай однократную настройку репозитория для серии задач по созданию RASA HR-бота.
Это «нулевой» шаг — кода фичей пока не пишем, только инфраструктуру.

КОНТЕКСТ
В корне репозитория уже лежат два примера: `01_hello_bot/` и `02_phones_bot/`.
Мы будем добавлять `03_hr_bot/`. Конвенции (язык, структура файлов, pipeline) —
как в `02_phones_bot`. Окружение — Python 3.10 + RASA 3.6.x, см. SETUP_PYTHON.md.

ЦЕЛЬ
1. Проверить git-репозиторий (есть ли remote, на какой ветке).
2. Создать корневой `CLAUDE.md` с правилами проекта.
3. Создать `.claude/commands/` со слэш-командами:
   - `/rasa-check` — `rasa data validate` + `rasa train --quiet` для текущего бота,
     с краткой сводкой ошибок.
   - `/smoke` — стартует action server и rasa REST API на фоне, шлёт 2–3 curl-запроса,
     гасит процессы.
   - `/ship <type>: <message>` — `git add -A && git commit -m "<type>: <message>"` +
     `git push`. Тип — conventional (feat/fix/docs/chore/refactor/test).
4. Создать `.claude/agents/` с subagent-определениями:
   - `rasa-validator` — sonnet, инструменты Bash+Read+Grep; запускает валидацию и тренировку,
     возвращает компактный отчёт «✅/❌ + причины».
   - `dialog-designer` — opus (если нет — sonnet), инструменты Read+Write+Edit; проектирует
     intents/entities/slots/stories, никогда не запускает обучение.
   - `actions-engineer` — sonnet, инструменты Read+Write+Edit+Bash; пишет actions.py,
     валидирует через `python -m py_compile`.
   - `qa-tester` — sonnet, инструменты Bash+Read; гоняет curl-сценарии и `rasa test`,
     возвращает таблицу пройденных/упавших сценариев.
5. Если remote `origin` отсутствует, спроси у меня, создать ли репозиторий на GitHub
   через `gh repo create` (имя — `rasa-seminar-examples`, видимость — private).
   Не догадывайся: сначала спроси, потом действуй.
6. Создать ветку `feat/hr-bot` от текущего main/master, переключиться на неё.
7. В корневой `.gitignore` добавить (если нет):
   `models/`, `.rasa/`, `__pycache__/`, `*.pyc`, `.venv/`, `results/`, `*.tar.gz`.

ОГРАНИЧЕНИЯ
- Не трогай `01_hello_bot/` и `02_phones_bot/`.
- В `CLAUDE.md` запиши минимум: язык бота (русский), версии (Python 3.10, RASA 3.6.x),
  правило «после каждой фичи — /rasa-check, затем /ship», правило «новые слоты/интенты/
  сущности всегда сначала описываются в domain.yml».
- Слэш-команды и сабагенты пиши в формате Claude Code (frontmatter YAML, тело — инструкции).

КРИТЕРИИ ГОТОВНОСТИ
- `ls .claude/commands/` показывает 3 файла, `ls .claude/agents/` — 4.
- `git status` чистый, мы на ветке `feat/hr-bot`.
- `git log -1` показывает коммит `chore: scaffold claude code config for hr-bot`.
- `git push -u origin feat/hr-bot` отработал.

В конце выведи краткий чек-лист «что готово» и предложи мне передать следующий промпт.
```

---

## Промпт 1 — план MVP в plan mode

```text
Перейди в plan mode (Shift+Tab) и спроектируй MVP HR-бота, НЕ ПИСАВ КОД.

КОНТЕКСТ
Бот — first-line интервьюер для скрининга кандидатов на одну из 5 ролей ML-команды:
Project Manager, Data Analyst, Data Engineer, Data Scientist, MLOps Engineer.
Архитектурный референс — `02_phones_bot/` (forms, slots, custom actions, CSV-база).
Подробное описание задачи — в `HR_BOT_CLAUDE_CODE_PROMPTS.md`, секция «Что мы строим».

Делегируй проектирование сабагенту `dialog-designer` (см. `.claude/agents/`). Я хочу
получить конкретный артефакт-документ, а не «общие рассуждения в чате».

ЦЕЛЬ
Спроектировать и сохранить документ `03_hr_bot/DESIGN.md` со следующими секциями:

1. **Сценарий MVP** — happy-path диалог из ~10 реплик (Кандидат / Бот) для роли DS.
2. **Sad-path сценарии** (минимум 3): пользователь отказывается отвечать; не подходит ни
   под одну роль; запрос вне области (out_of_scope).
3. **Intents** (имя → 1 строка описания). Минимум: greet, goodbye, start_interview,
   inform (общий «дать ответ»), affirm, deny, ask_about_role, restart, bot_challenge,
   out_of_scope. Каждый — с 2–3 примерами фраз.
4. **Entities** — таблица «имя | тип извлечения | где используется». Минимум:
   - `role` (DIET + lookup table + synonyms, маппится в слот desired_role)
   - `years_experience` (regex `\d+`)
   - `skill` (lookup table со списком ML-навыков)
   - `salary_amount` (regex для денежных сумм)
   - `email` (regex)
   - `full_name` (DIET)
5. **Slots** — таблица «имя | тип | влияет_ли_на_диалог | mapping». Список:
   candidate_name, candidate_email, desired_role (categorical из pm/da/de/ds/mlops),
   years_experience (float), skills (list), expected_salary (float),
   assessment_decision (categorical pass/fail/alternative).
6. **Form `interview_form`** — required_slots в правильном порядке, плюс ответы
   `utter_ask_<slot>` (по 1 формулировке на старт, можно с кнопками для desired_role).
7. **Custom actions**:
   - `validate_interview_form` — пер-слотовая валидация (email regex, опыт ≥ 0, роль в списке).
   - `action_assess_candidate` — читает `roles_requirements.csv`, сравнивает с собранными
     слотами, возвращает решение pass/fail/alternative и текстовый фидбек.
   - `action_offer_alternative_role` — предлагает смежную роль (например, DS без опыта
     ML-моделирования → DA).
   - `action_reset_interview` — сбрасывает все слоты по интенту `restart`.
8. **`roles_requirements.csv`** — схема: role, role_name, min_years, required_skills
   (через `;`), salary_min, salary_max, alternative_role. Привести готовые данные на 5 ролей
   (можно с пометкой «черновик, уточним»).
9. **Pipeline / policies** — взять из `02_phones_bot/config.yml`, отметить что менять
   (вероятно, ничего не менять — те же DIET, EntitySynonymMapper, RulePolicy, TEDPolicy).
10. **Дорожная карта** — нумерованный список из 7–10 итераций, каждая со своим коммитом.
    Это станет основой для последующих промптов.

ОГРАНИЧЕНИЯ
- НЕ ПИШИ КОД. Только проектируй и сохраняй в DESIGN.md.
- Используй plan mode: дай мне посмотреть план до сохранения файла.
- Не выдумывай дополнительные интенты «на всякий случай» — MVP должен оставаться
  минимальным (≤ 12 интентов).

КРИТЕРИИ ГОТОВНОСТИ
- Файл `03_hr_bot/DESIGN.md` создан.
- Все 10 секций есть, без TODO внутри (кроме явно помеченных «уточним позже»).
- В конце ответа дай мне дорожную карту в виде нумерованного списка — я буду по ней
  выдавать следующие промпты.

После моего одобрения плана: выйди из plan mode, сохрани DESIGN.md, вызови
`/ship docs: add design document for hr-bot MVP`.
```

---

## Промпт 2 — скелет проекта (рыбий хвостик)

```text
Создай минимальный работающий скелет `03_hr_bot/` — RASA-проект, который проходит
`rasa data validate` и `rasa train`, но пока умеет только greet/goodbye/out_of_scope
и запускать пустую interview_form.

КОНТЕКСТ
- DESIGN.md уже лежит в `03_hr_bot/`. Используй его как источник истины.
- Делай по образцу `02_phones_bot/` — те же файлы, тот же стиль комментариев, тот же
  config.yml (только assistant_id перегенерируем).
- Все шаблоны ответов — на русском.

ЦЕЛЬ
Создать в `03_hr_bot/`:
1. `domain.yml` — версия 3.1; intents greet, goodbye, out_of_scope, bot_challenge,
   start_interview, restart; пустые слоты-заглушки для всех слотов из DESIGN.md
   (тип text, influence_conversation: false, mappings: from_text — заполним позже);
   responses utter_greet, utter_goodbye, utter_out_of_scope, utter_iamabot,
   utter_introduce_bot (короткое описание роли бота), utter_ask_start_interview;
   form `interview_form` с required_slots = [] (пустой!) — заполним в следующем промпте;
   session_config с carry_over_slots_to_new_session: false.
2. `data/nlu.yml` — по 6–10 примеров на каждый интент. Брать формулировки из
   DESIGN.md и расширять.
3. `data/rules.yml` — правила для greet, goodbye, out_of_scope, bot_challenge,
   start_interview (запускает форму), restart (вызывает `action_reset_interview`
   — пока заглушка, перечислим в actions).
4. `data/stories.yml` — 2–3 happy-path истории из DESIGN.md (можно без слотов пока).
5. `config.yml` — копия `02_phones_bot/config.yml`, удали строку assistant_id
   (RASA дополнит сама при `rasa train`).
6. `endpoints.yml` — стандартный, указывающий action_endpoint на localhost:5055.
7. `actions/actions.py` — заглушки классов ActionResetInterview,
   ActionAssessCandidate, ActionOfferAlternativeRole (метод `name()` + `run()`,
   возвращающий пустой список). Это нужно, чтобы `rasa train` не ругалась на
   undefined actions из rules.yml.
8. `README.md` — по образцу `02_phones_bot/README.md`, секции «Цель»,
   «Что нового по сравнению с 02_phones_bot», «Команды запуска», «Сценарии диалога»
   (заглушка с TODO).

ВАЛИДАЦИЯ
Вызови `/rasa-check` — должен пройти валидацию и обучить модель без ошибок.
Игнорируем только предупреждения вида «utter_ask_... not used» — это нормально
для slot-filling форм.

Если валидация падает — НЕ КОММИТЬ. Сначала чини, потом коммит.

КРИТЕРИИ ГОТОВНОСТИ
- `rasa data validate` без ошибок (предупреждения допустимы).
- `rasa train` создаёт модель в `03_hr_bot/models/`.
- Файлы оформлены по стилю `02_phones_bot` (комментарии-разделители `# ── ... ──`).

КОММИТ
`/ship feat(hr-bot): scaffold project skeleton with empty interview form`
```

---

## Промпт 3 — выбор роли через кнопки и categorical-слот

```text
Добавь первый «реальный» слот формы: `desired_role`.

КОНТЕКСТ
- Скелет `03_hr_bot/` уже работает (Промпт 2 завершён).
- Пользователь должен мочь выбрать роль либо текстом («хочу как Data Scientist»),
  либо нажав одну из 5 кнопок.
- Используем сабагент `dialog-designer` для проектирования примеров фраз и
  lookup table (помни про синонимы: «дата-сайентист» / «DS» / «ML-инженер по моделям»).

ЦЕЛЬ
1. В `domain.yml`:
   - Добавить entity `role`.
   - Превратить слот `desired_role` в categorical с values [pm, da, de, ds, mlops],
     `influence_conversation: true`, mapping `from_entity entity: role`.
   - Добавить в `interview_form.required_slots` единственный пункт: `desired_role`.
   - Добавить `utter_ask_desired_role` с buttons (5 кнопок: payload = `/inform{"role":"pm"}` и т.д.).
   - Добавить `utter_role_chosen` — «Записал, рассматриваем тебя как {desired_role}.»
2. В `data/nlu.yml`:
   - Добавить интент `inform` (или расширить существующий) с примерами разметки [pm](role),
     [Data Scientist](role), [мл-опс](role) и т.д.
   - Добавить секцию `lookup` `role` со списком синонимов.
   - Добавить секции `synonym` для нормализации в pm/da/de/ds/mlops.
3. В `data/rules.yml`:
   - Добавить правило «После заполнения interview_form — вызвать utter_role_chosen»
     (пока без action_assess_candidate; ассессмент включим в Промпте 7).
4. В `data/stories.yml`:
   - Добавить story «выбор роли через кнопку» и «выбор роли текстом».

ВАЛИДАЦИЯ
`/rasa-check` + ручная проверка через `/smoke`:
- POST /webhooks/rest/webhook `{"sender":"u1","message":"Хочу пройти интервью"}`
  → бот предлагает выбрать роль (текст + кнопки).
- POST `{"sender":"u1","message":"/inform{\"role\":\"ds\"}"}`
  → бот отвечает utter_role_chosen с подставленной ролью.
- POST `{"sender":"u2","message":"Я data engineer"}`
  → entity role=de, слот заполнен.

Если любой из 3 кейсов проваливается — чини, потом коммитимся.

КРИТЕРИИ ГОТОВНОСТИ
- `/rasa-check` зелёный.
- 3 curl-сценария выше работают.
- В DESIGN.md обновлён статус пункта «desired_role» как «✅ реализован».

КОММИТ
`/ship feat(hr-bot): collect desired_role via buttons and free text`
```

---

## Промпт 4 — контактные данные (имя + email) с regex и валидацией

```text
Добавь сбор контактных данных кандидата: имя и email. Активируй пер-слотовую валидацию
формы через `validate_interview_form`.

ЦЕЛЬ
1. В `domain.yml`:
   - Слот `candidate_name`: type text, mapping from_entity entity: full_name + fallback
     from_text (если NER не извлёк).
   - Слот `candidate_email`: type text, mapping from_entity entity: email.
   - Добавить в `interview_form.required_slots` в начало: candidate_name, candidate_email.
   - Ответы utter_ask_candidate_name, utter_ask_candidate_email.
   - utter_invalid_email — «Email выглядит странно, проверь, пожалуйста.»
2. В `data/nlu.yml`:
   - Regex `email`: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`.
   - Расширить примеры intent inform: [Иван Петров](full_name), мой email
     [ivan@example.com](email) и т.д.
3. В `config.yml`:
   - Добавить RegexEntityExtractor ПОСЛЕ DIETClassifier (нужен для email — он
     слишком хорошо ловится регулярным выражением и DIET его «прозевает» на коротких
     примерах). Не добавляй для role — там lookup внутри DIET уже работает.
4. В `actions/actions.py`:
   - Класс `ValidateInterviewForm(FormValidationAction)` с двумя методами:
     `validate_candidate_name` (минимум 2 слова, иначе SlotSet None + сообщение),
     `validate_candidate_email` (regex check ещё раз, иначе SlotSet None).
   - Используй `from rasa_sdk.forms import FormValidationAction`.
5. В `domain.yml` зарегистрируй action `validate_interview_form` в секции actions.

⚠️ ВАЖНО ПРО REGEX ЭКСТРАКТОРЫ
В `02_phones_bot/config.yml` явно сказано «RegexEntityExtractor намеренно НЕ добавляем».
Прочитай комментарий в том файле. У нас другая ситуация: для email regex нужен, для role —
нет. Поэтому regex для email определи через секцию `regex` в nlu.yml, а
RegexEntityExtractor в pipeline добавь только если без него email не извлекается на
смоук-тестах. Сначала попробуй БЕЗ него (DIET + regex secten в nlu.yml). Если смоук падает
— добавь и зафиксируй причину в комментарии в config.yml.

ВАЛИДАЦИЯ
- `/rasa-check`.
- `/smoke` сценарий полного диалога:
  1. start_interview → бот спрашивает имя
  2. «Иван» → ругается, что нужно ФИ
  3. «Иван Петров» → принимает, спрашивает email
  4. «ivan» → ругается, невалидный email
  5. «ivan@example.com» → принимает, спрашивает роль
  6. Кнопка DS → форма завершается
- Делегируй валидацию сабагенту `qa-tester`, он вернёт таблицу пройденных/упавших.

КРИТЕРИИ ГОТОВНОСТИ
- 6 шагов смоук-теста проходят.
- `validate_interview_form` действительно вызывается (видно в логах action server).

КОММИТ
`/ship feat(hr-bot): collect candidate name and email with form validation`
```

---

## Промпт 5 — опыт и навыки (числовая сущность + lookup-таблица навыков)

```text
Добавь сбор количества лет опыта и списка навыков кандидата.

ЦЕЛЬ
1. В `domain.yml`:
   - Слот `years_experience`: type float, mapping from_entity entity: years_experience.
   - Слот `skills`: type list, mapping from_entity entity: skill (поведение по умолчанию
     — добавляет в список при каждом извлечении).
   - В `interview_form.required_slots` добавить: years_experience, skills.
   - Ответы utter_ask_years_experience, utter_ask_skills, utter_invalid_experience.
2. В `data/nlu.yml`:
   - Regex `years_experience`: `(\d+)\s*(лет|год|года|years?)?`.
   - Lookup table `skill` — собери список из ~30 типичных ML/инженерных навыков
     (Python, SQL, pandas, scikit-learn, PyTorch, TensorFlow, Spark, Airflow, Docker,
     Kubernetes, Kafka, ClickHouse, Snowflake, A/B-testing, NLP, CV, RecSys, LLM,
     RAG, MLflow, dbt, Tableau, …). Группируй по ролям логически (комментарием).
   - Примеры в intent inform с разметкой [Python](skill), [SQL](skill), [3 года](years_experience).
3. В `actions/actions.py`:
   - Метод `validate_years_experience` — приводит к float, валидирует 0–50.
   - Метод `validate_skills` — нормализует регистр, дедуплицирует, минимум 1 навык
     (иначе переспрос).
4. В `config.yml` — убедись, что lookup table для skill реально влияет на DIET
   (через CountVectorsFeaturizer char_wb 2–4). При желании добавь EntitySynonymMapper
   для случаев «питон» → «python», «постгрес» → «postgresql».

ВАЛИДАЦИЯ
- `/rasa-check`.
- Сабагент `qa-tester` гоняет смоук:
  1. После email бот спрашивает опыт.
  2. «5 лет» → слот заполнен (5.0).
  3. После опыта бот спрашивает навыки.
  4. «Python, SQL и немного PyTorch» → слот skills = [python, sql, pytorch] (с учётом нормализации).
  5. Спросить про роль (если ещё не спрашивал) → ответ.
  6. Форма завершилась с заполненными слотами candidate_name, candidate_email,
     desired_role, years_experience, skills.

КРИТЕРИИ ГОТОВНОСТИ
- Все 6 шагов смоук-теста проходят.
- Логи action server показывают валидацию обоих новых слотов.

КОММИТ
`/ship feat(hr-bot): capture years of experience and skill list`
```

---

## Промпт 6 — ожидаемая зарплата с regex-сущностью

```text
Добавь последний обязательный слот формы: `expected_salary`.

ЦЕЛЬ
1. В `domain.yml`:
   - Слот `expected_salary`: type float, mapping from_entity entity: salary_amount.
   - Добавить в `interview_form.required_slots` (в конец).
   - Ответы utter_ask_expected_salary, utter_invalid_salary.
2. В `data/nlu.yml`:
   - Regex `salary_amount`: ловить варианты «150000», «150 000», «150к», «150 тысяч»,
     «150000 ₽», «300 000 руб». Спроектируй ОДИН regex или несколько (RegexEntityExtractor
     поддерживает мульти-паттерны на один entity name).
   - Примеры в inform: [150000](salary_amount), хочу [200 тысяч](salary_amount),
     ожидаемая [300к](salary_amount).
3. В `actions/actions.py`:
   - Метод `validate_expected_salary` — конвертирует строки вроде «150к», «150 тысяч»,
     «150 000 ₽» в float. Если получилось < 50_000 или > 1_500_000 — переспросить.
   - Используй вспомогательную функцию `_parse_salary(text: str) -> float | None`,
     покрой её юнит-тестами через docstring-doctest или отдельным `tests/test_actions.py`.

ВАЛИДАЦИЯ
- `/rasa-check`.
- Юнит-тест: `pytest 03_hr_bot/tests/test_actions.py` (если создал) — проходит.
- `/smoke` — полный happy-path до завершения формы со всеми 6 слотами.

КРИТЕРИИ ГОТОВНОСТИ
- Все парсинги зарплаты («150к», «150 000», «150 тысяч») возвращают 150000.0.
- Форма завершается, бот говорит utter_role_chosen.

КОММИТ
`/ship feat(hr-bot): parse expected salary with flexible regex`
```

---

## Промпт 7 — движок ассессмента: action_assess_candidate

```text
Самая интересная итерация: научи бота ПРИНИМАТЬ РЕШЕНИЕ по итогам собранных данных.

КОНТЕКСТ
- Все 6 слотов формы заполнены (candidate_name, candidate_email, desired_role,
  years_experience, skills, expected_salary).
- В DESIGN.md есть схема `roles_requirements.csv` и черновые значения.

ЦЕЛЬ
1. Создать `03_hr_bot/roles_requirements.csv` с финальными данными по 5 ролям:
   - колонки: role, role_name, min_years, required_skills (через `;`),
     nice_to_have_skills (через `;`), salary_min, salary_max, alternative_role
   - конкретные требования спроектируй здраво: PM — soft skills, опыт ≥ 2 года, без
     hard ML; DA — SQL/Python/Tableau, 1+ год; DE — Spark/Airflow/Kafka, 2+ год;
     DS — Python/sklearn/PyTorch, 2+ год; MLOps — Docker/K8s/MLflow, 3+ год.
   - alternative_role — заполни осмысленно (DS не подошёл по опыту → DA; DE не подошёл
     → DS; MLOps → DE; PM → нет альтернативы → пусто).
2. Реализовать `ActionAssessCandidate` в `actions/actions.py`:
   - Загрузка CSV через pandas (как в `02_phones_bot`).
   - Логика:
     - `match_required = required_skills ⊆ set(skills)` (нормализованный регистр).
     - `match_years = years_experience >= min_years`.
     - `match_salary = expected_salary <= salary_max` (опционально: если > salary_max,
        предупреждаем, но не отказываем).
     - Если `match_required AND match_years` → `pass`, сообщить «Ты подходишь, пригласим
       на следующий этап».
     - Если `match_years AND not match_required` → `alternative` (предложить
       alternative_role, если есть).
     - Если `not match_years` → `fail` с конкретикой «Требуется N+ лет, у тебя M».
     - Если `expected_salary > salary_max` → префикс ответа «Учти, бюджет до X ₽».
   - Возвращает `SlotSet("assessment_decision", "pass"/"fail"/"alternative")` +
     dispatcher.utter_message с подробным фидбеком.
3. Добавить `ActionOfferAlternativeRole`:
   - Если decision == "alternative" и alternative_role не пуст — спросить «Хочешь
     обсудить роль X?» с кнопками Да/Нет.
   - Если пользователь говорит affirm — сбрасывает desired_role на alternative_role,
     ставит остальные слоты в None, активирует interview_form заново.
4. Обновить `data/rules.yml`:
   - После заполнения формы вызывать `action_assess_candidate`.
   - На decision == "alternative" вызывать `action_offer_alternative_role`.
5. Обновить `data/stories.yml`:
   - 3 happy-path: pass, fail, alternative-accept (кандидат согласился на альтернативу).
   - 1 sad-path: alternative-deny (кандидат отказался, прощаемся).

ВАЛИДАЦИЯ
- `/rasa-check`.
- Сабагент `qa-tester` гоняет 4 сценария по REST API:
  1. PASS: DS, 5 лет, [Python, sklearn, PyTorch], 200000 → решение pass.
  2. FAIL: DS, 0 лет, [Python] → решение fail.
  3. ALTERNATIVE-ACCEPT: DS, 5 лет, [SQL, Python, Tableau] → предлагает DA, кандидат
     соглашается → форма перезапускается.
  4. ALTERNATIVE-DENY: то же, но deny → прощание.

КРИТЕРИИ ГОТОВНОСТИ
- Все 4 сценария дают ожидаемые тексты ответа.
- `assessment_decision` действительно проставляется в tracker (видно в `/conversations/<id>/tracker`).

КОММИТ
`/ship feat(hr-bot): implement candidate assessment engine with role fallback`
```

---

## Промпт 8 — sad-path: рестарт, отказ отвечать, out_of_scope в середине формы

```text
Добавь устойчивость к нестандартным траекториям диалога.

ЦЕЛЬ
1. Реализовать `ActionResetInterview` (была заглушкой):
   - Сбрасывает все слоты формы в None.
   - Деактивирует `interview_form` (event `ActiveLoop(None)`).
   - Сообщает «Начинаем сначала. С кем тебя записать?»
2. В `data/nlu.yml` — расширить интент `restart` (8–10 примеров: «давай заново»,
   «сбрось», «начнём с начала», «restart», ...).
3. В `data/rules.yml` — правило: на intent restart — `action_reset_interview`,
   даже внутри active_loop.
4. Поведение при out_of_scope ВНУТРИ формы:
   - В `domain.yml` → form `interview_form` → `ignored_intents: [out_of_scope]`
     НЕ ставим — это запретит обработку. Вместо этого добавь stories:
     «бот спрашивает имя — пользователь out_of_scope — бот говорит "сначала ответь на
     вопросы интервью" — продолжает форму».
   - Ответ `utter_please_continue_form` — «Сначала закончим интервью, потом обсудим
     остальное.»
5. Поведение при `deny` на utter_ask_start_interview:
   - Story: greet → utter_introduce_bot → utter_ask_start_interview → deny → utter_goodbye.
6. Bot challenge: расширить `utter_iamabot` — «Да, я HR-бот для первичного скрининга.
   Решения о найме принимают живые рекрутёры.»

ВАЛИДАЦИЯ
- `/rasa-check`.
- Смоук от `qa-tester`:
  1. Начало → restart на любом шаге → форма сбрасывается.
  2. Начало → out_of_scope на шаге email → бот возвращает к вопросу про email.
  3. greet → deny → goodbye без активации формы.

КРИТЕРИИ ГОТОВНОСТИ
- 3 сценария проходят.
- TEDPolicy на этих историях не предсказывает «утечку» в pass/fail/assess (можно
  проверить через `rasa interactive` локально, если есть время — необязательно).

КОММИТ
`/ship feat(hr-bot): handle restart, out_of_scope inside form, and bot challenge`
```

---

## Промпт 9 — авто-тесты на основе story-файлов и юнит-тесты для actions

```text
Закрепи поведение бота тестами, чтобы будущие правки не сломали логику.

ЦЕЛЬ
1. Создать `03_hr_bot/tests/test_stories.yml` в формате RASA stories — минимум 6
   сценариев (3 pass-path, 3 sad-path). Это **regression-тесты**, формат тот же, что
   у обычных stories.
2. Создать `03_hr_bot/tests/test_actions.py`:
   - Тесты для `_parse_salary` (8+ кейсов: 150000, "150к", "150 тысяч", "150 000 ₽",
     невалидные строки).
   - Тесты для assessment-логики (через прямой вызов класса action с замоканным
     tracker — гугли паттерн `Tracker.from_dict` / `MockDispatcher`).
3. Создать `03_hr_bot/Makefile` (если на Windows — `tasks.ps1`) с целями:
   - `make train` → `rasa train`
   - `make validate` → `rasa data validate`
   - `make test` → `rasa test --stories tests/test_stories.yml` + `pytest tests/`
   - `make smoke` → запуск REST + curl-проверки + остановка
   - `make clean` → удалить `models/`, `.rasa/`, `results/`
4. Обновить `03_hr_bot/README.md`: секция «Тесты» с описанием `make test` и
   ссылками на `tests/`.

ВАЛИДАЦИЯ
- `make test` зелёный (или эквивалент на Windows).
- `rasa test` создал директорию `results/` — добавь её в `.gitignore` если ещё нет.

КРИТЕРИИ ГОТОВНОСТИ
- pytest проходит.
- rasa test stories проходит без `failed_test_stories.yml` в результатах.

КОММИТ
`/ship test(hr-bot): add regression tests for stories and action unit tests`
```

---

## Промпт 10 — финальный README, чек-лист демо, PR

```text
Финальная итерация: документация, демо-инструкции и Pull Request.

ЦЕЛЬ
1. Полностью переписать `03_hr_bot/README.md` по схеме `02_phones_bot/README.md`:
   - Педагогическая цель.
   - Что нового по сравнению с 02_phones_bot (новые концепты: categorical-slot,
     FormValidationAction, multi-step decision action, regex+lookup combo).
   - Сценарии диалога (3 примера: pass, fail, alternative).
   - База `roles_requirements.csv` (что в ней, как править).
   - Команды запуска (с примерами curl-запросов).
   - Структура файлов (дерево).
   - Чек-лист отладки (как в `02_phones_bot/README.md`, секция «Чек-лист при отладке»).
   - Идеи для домашнего задания — 4–5 пунктов.
2. Обновить корневой `CLAUDE.md`: добавить ссылку на `03_hr_bot/` как пример «полного
   цикла» — entities/forms/actions/tests/CI.
3. Очистить `03_hr_bot/`:
   - Удалить любые `models/*.tar.gz` (есть в .gitignore, но могли остаться).
   - Удалить `.rasa/cache/` если остался.
   - `git status` должен быть чистым.
4. Создать Pull Request:
   - Используй `gh pr create --base main --head feat/hr-bot --title "feat: add HR
     candidate screening bot" --body @PR_BODY.md`.
   - `PR_BODY.md` сгенерируй автоматически: список фич (буллеты по коммитам),
     скриншоты curl-выводов 3 happy-сценариев (текстом, не картинками), TODO
     для следующих итераций.
5. Не мерджи PR сам — оставь мне на ревью.

ВАЛИДАЦИЯ
- `gh pr view` показывает PR в браузер-формате.
- README рендерится без поломок (`grip 03_hr_bot/README.md` если есть, или просто
  визуальный просмотр).

КРИТЕРИИ ГОТОВНОСТИ
- PR создан, ссылка выведена в чат.
- README покрывает все секции из чек-листа выше.

КОММИТ
`/ship docs(hr-bot): final README, demo checklist, and PR`
```

---

## Бонусные промпты (по желанию)

### Бонус А — Telegram-канал

```text
Подключи бота к Telegram через стандартный коннектор RASA.

ЦЕЛЬ
1. `credentials.yml`: добавить секцию telegram с access_token, verify, webhook_url
   (читать из переменных окружения, НЕ хардкодить).
2. README — секция «Подключение к Telegram»: как создать бота через @BotFather,
   как пробросить webhook через ngrok / cloudflare tunnel.
3. Не коммить .env / credentials.yml с реальными токенами — добавь в .gitignore
   `credentials.local.yml` и используй его.

КОММИТ
`/ship feat(hr-bot): telegram channel integration`
```

### Бонус Б — CI на GitHub Actions

```text
Добавь CI: при push в любую ветку — гонять валидацию и тесты бота.

ЦЕЛЬ
1. `.github/workflows/rasa-ci.yml`:
   - python-version: 3.10
   - matrix по каждому из 3 ботов (01_hello, 02_phones, 03_hr).
   - шаги: install rasa==3.6.*, rasa data validate, rasa train --quiet, pytest tests/
     (если есть), rasa test --stories tests/test_stories.yml (если есть).
   - кешировать pip / rasa cache между запусками.
2. Бэйдж статуса в корневой README.md.

КОММИТ
`/ship ci: add github actions workflow for rasa bots`
```

### Бонус В — A/B-сравнение моделей

```text
Сравни два варианта config.yml (DIET 100 vs 200 эпох + ResponseSelector) по метрикам
NLU и core. Цель — научиться использовать `rasa test --cross-validation`.

ЦЕЛЬ
1. `03_hr_bot/configs/baseline.yml` и `experiment.yml`.
2. `make experiment` — запускает cross-validation для обоих, кладёт отчёты в
   `results/baseline/` и `results/experiment/`.
3. README — таблица сравнения F1, точности интентов, accuracy core.

КОММИТ
`/ship experiment: compare two pipeline configs with cross-validation`
```

---

## Шпаргалка по «вайбкодингу» с Claude Code

| Принцип | Как применяем здесь |
|---|---|
| **Plan mode перед кодом** | Промпт 1 целиком в plan mode — заставляем Claude спроектировать, прежде чем писать. |
| **Сабагенты для фокусировки** | `dialog-designer` не запускает обучение; `qa-tester` не пишет код. Каждый делает одно. |
| **Слэш-команды для рутины** | `/rasa-check`, `/smoke`, `/ship` — то, что повторяется 10+ раз за проект. |
| **Один коммит — одна фича** | Каждый промпт заканчивается `/ship` с conventional-сообщением. |
| **Чёткие критерии готовности** | В каждом промпте секция «КРИТЕРИИ ГОТОВНОСТИ» — Claude знает, когда остановиться. |
| **Валидация в самом промпте** | Не «когда-нибудь проверим», а явные curl-сценарии и `/rasa-check` перед коммитом. |
| **Память проекта** | `CLAUDE.md` + `DESIGN.md` — Claude перечитывает их в начале каждой сессии. |
| **PR в конце, а не мердж** | Промпт 10 создаёт PR, но не мерджит — человек смотрит финальный диф. |

---

## Если что-то пошло не так

- **Claude начал писать код в plan mode** → напомни ему: «ты в plan mode, только проектируем».
- **`rasa train` падает на TensorFlow** → проверь Python 3.10, не 3.11+.
- **Сабагент не вызывается** → проверь, что файл лежит в `.claude/agents/` с корректным
  YAML frontmatter (`name`, `description`, `tools`, `model`).
- **Слэш-команда `/ship` коммитит лишнее** → у тебя в .gitignore нет `models/` или `.rasa/`.
  Откати последний коммит: `git reset HEAD~1`, поправь .gitignore, повтори `/ship`.
- **Бот игнорирует кнопки** → в payload должен быть `/intent_name{"slot":"value"}`, а не
  просто текст кнопки.
- **Форма зацикливается** → одна из required_slots не маппится. Прогон `rasa shell` с
  `--debug` покажет, какой слот бот пытается заполнить.
