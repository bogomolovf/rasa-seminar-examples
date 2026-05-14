# Проект: RASA HR-бот (rasa-seminar-examples)

## Что это
Учебный репозиторий с примерами RASA-ботов. Текущая активная работа — `03_hr_bot/`.

Структура:
- `01_hello_bot/` — пример «hello world». **Не редактировать.**
- `02_phones_bot/` — пример с формами и lookup-таблицей. **Не редактировать.** Используется как референс по структуре и pipeline.
- `03_hr_bot/` — HR-бот, пример «полного цикла»: форма с per-slot валидацией (`FormValidationAction`), decision-action на CSV (`roles_requirements.csv` + `ActionAssessCandidate`), sad-paths (`restart_interview`/`out_of_scope` внутри формы), регрессионные тесты (`tests/test_stories.yml` + `pytest`) и `Makefile` (`make all`). Разбор по итерациям — `HR_BOT_CLAUDE_CODE_PROMPTS.md`; финальная документация — `03_hr_bot/README.md`.

## Стек и язык
- **Python 3.10**, **RASA 3.6.x** (см. `SETUP_PYTHON.md` / `SETUP_ANACONDA.md`).
- Окружение: conda-managed venv в `./.venv` (создано через `conda create -p ./.venv python=3.10`).
- **Используй прямой путь к binary:** `./.venv/bin/rasa ...` или `./.venv/bin/python -m rasa ...`. Conda prefix-env не имеет `bin/activate` скрипта; для интерактивной shell — `conda activate /Users/fedorbogomolov/Desktop/examples/.venv`.
- Бот разговаривает **на русском**. NLU-примеры, ответы (`utter_*`), кнопки — на русском.
- Код, переменные, имена интентов/сущностей/слотов — на английском (`inform_role`, `email`, `years_experience` и т.п.).
- Конвенции структуры (config.yml pipeline/policies, размещение actions, формат данных) — как в `02_phones_bot`.

## Правила работы

### 1. Сначала domain, потом всё остальное
Любая новая сущность контракта диалога — **сначала в `domain.yml`**, потом в данных/коде:
- Новый **slot** → добавить в `slots:` (с типом и `mappings`), потом ссылаться в формах/действиях.
- Новый **intent** → добавить в `intents:`, потом писать примеры в `data/nlu.yml`.
- Новая **entity** → добавить в `entities:`, потом в NLU и (если нужно) в `slots.<slot>.mappings`.
- Новое **action** / **form** → объявить в `actions:` / `forms:`, потом писать код / правила.

Это предотвращает ошибки вида «slot was set but not declared», молчаливый дрейф между data и кодом, и невалидные обучения.

### 2. После каждой фичи — `/rasa-check`, затем `/ship`
- **`/rasa-check`** — валидирует данные и прогоняет короткое обучение. Если падает — чиним до зелёного, **не коммитим красное**.
- **`/ship <type>: <message>`** — стейджит, коммитит conventional-сообщением и пушит. Тип строго один из: `feat | fix | docs | chore | refactor | test`.

Порядок: меняем код → `/rasa-check` зелёный → `/ship feat: добавил слот role`. Не наоборот.

### 3. Тестовые прогоны через `/smoke`
Перед `/ship` крупной фичи (новый flow, новый action) — `/smoke`: поднимает action server + REST API, шлёт curl-запросы, гасит процессы. Используется как быстрый sanity-check end-to-end.

### 4. Делегирование специализированным агентам
Доступны subagent'ы в `.claude/agents/`:
- `rasa-validator` — для проверки данных и обучения.
- `dialog-designer` — для проектирования intents/entities/slots/stories (НЕ запускает обучение).
- `actions-engineer` — для написания `actions.py` (валидирует через `py_compile`).
- `qa-tester` — для curl-сценариев и `rasa test`.

Используй их через Agent tool, когда задача чётко попадает в роль. Для общих правок (README, мелкая правка yml) — работай напрямую.

### 5. Что не коммитим
В `.gitignore` уже: `models/`, `.rasa/`, `__pycache__/`, `*.pyc`, `.venv/`, `results/`, `*.tar.gz`, `.DS_Store`. Обученные модели и кеш — никогда в репо.

## Workflow в одну строку
`/rasa-check` → fix → `/smoke` (если фича крупная) → `/ship <type>: <message>`.
