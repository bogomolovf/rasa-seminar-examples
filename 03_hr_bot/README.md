# 03_hr_bot — HR-ассистент первичного скрининга

## Педагогическая цель

Показать, как собрать **диалогового агента под бизнес-задачу** (HR-скрининг
кандидатов на 5 ролей ML-команды) на RASA 3.6: проектирование контракта
диалога (intents/entities/slots), форма с per-slot валидацией, custom
actions с обращением к CSV-таблице требований, sad-path-сценарии
(отказ, сброс, out-of-scope).

Полная спецификация — `DESIGN.md` в корне примера.

## Что нового по сравнению с `02_phones_bot`

| Концепт | Где появится | Что показывает |
|---|---|---|
| Форма с **6 required slots** | `domain.yml`, Промпты 3–6 | Длинный slot-filling с per-slot валидацией |
| **FormValidationAction** | `actions/actions.py`, Промпты 3–5 | `validate_<slot>` методы, нормализация ввода |
| **Categorical slot** | `domain.yml`, Промпт 3 | `desired_role` ∈ {pm, da, de, ds, mlops} с ветвлением |
| **List slot** | `domain.yml`, Промпт 5 | Накопление навыков через `from_entity` + CSV-парсер |
| **Float slot** + regex-парсер | `domain.yml`, Промпты 4–5 | Опыт в годах, зарплата в формате «250к» / «200 000» |
| **Lookup tables** на 2 сущности | `data/nlu.yml`, Промпты 3, 5 | `role` (≈ 15 синонимов) и `skill` (≈ 25 технологий) |
| **Assessment engine** | `actions/actions.py`, Промпт 6 | Сравнение слотов с `roles_requirements.csv`, решение pass/fail/alternative |
| **Buttons** в `utter_ask_*` | `domain.yml`, Промпт 3 | 5 кнопок выбора роли |
| **Sad-paths**: deny/restart | `data/rules.yml`, Промпт 7 | Отказ в форме, сброс через `action_reset_interview` |

> TODO (Промпты 3–10): таблица будет уточняться по мере появления фич.

## Текущий статус (Промпт 2)

Минимальный работающий скелет. Бот умеет:
- здороваться (`greet` → `utter_greet`),
- прощаться (`goodbye` → `utter_goodbye`),
- отвечать на «ты бот?» (`bot_challenge` → `utter_iamabot`),
- ловить out-of-scope (`out_of_scope` → `utter_out_of_scope`),
- запускать пустую `interview_form` по `start_interview`,
- сбрасывать состояние по `restart_interview` (через `action_reset_interview`-заглушку).

> Имя интента — `restart_interview`, а не `restart`: `/restart` зарезервирован
> RASA под встроенный `action_restart` и rule с предсказанием
> `action_reset_interview` приводит к `Contradicting rules`. Это уточнение
> к DESIGN.md §3 (там было `restart`).

Все 7 слотов из DESIGN.md объявлены, но пока имеют **тип `text` и
`mappings: [from_text]`** — реальные типы (categorical/float/list) и
правильные mapping'и появятся в Промптах 3–6.

## Команды запуска

```bash
# Активировать окружение (conda venv в ./.venv)
source ../.venv/bin/activate

# 1. В директории примера
cd 03_hr_bot

# 2. Обучить модель
rasa train

# 3. В отдельном терминале — action server (порт 5055)
rasa run actions

# 4. В основном терминале — чат
rasa shell
```

> На скелете (Промпт 2) `rasa shell` поддерживает только базовый flow:
> приветствие, запуск пустой формы, прощание. Полноценный скрининг
> заработает после Промптов 3–6.

## Сценарии диалога

TODO (заполнится в Промпте 10). Полный набор happy-path и sad-path
описан в `DESIGN.md` §1–2.

```
Пользователь: Привет
Бот: Привет! Я HR-ассистент команды ML. Помогу пройти первичный скрининг
     на одну из 5 ролей. Хотите начать собеседование?

Пользователь: Начать
Бот: (запускает interview_form — пока пустую)
```

## Структура каталога

```
03_hr_bot/
├── DESIGN.md          # спецификация контракта диалога
├── README.md          # этот файл
├── config.yml         # pipeline + policies (копия из 02_phones_bot)
├── domain.yml         # intents/entities/slots/responses/forms/actions
├── endpoints.yml      # http://localhost:5055/webhook
├── data/
│   ├── nlu.yml        # примеры на каждый intent
│   ├── rules.yml      # правила для greet/goodbye/out_of_scope/bot_challenge/start_interview/restart_interview
│   └── stories.yml    # 2–3 happy-path истории
└── actions/
    ├── __init__.py
    └── actions.py     # 4 класса-заглушки: ActionResetInterview, ActionAssessCandidate,
                       #   ActionOfferAlternativeRole, ValidateInterviewForm
```

## Тесты

В директории `tests/` лежат две группы тестов, обе запускаются одной командой
`make test` из `03_hr_bot/`:

1. **`tests/test_stories.yml`** — regression-stories, прогоняются через
   `rasa test --stories tests/test_stories.yml --out results/`. Покрывают
   6 сценариев (3 happy + 3 sad):
   - **PASS** — Data Scientist с полным стеком и опытом → `assessment_decision=pass`.
   - **FAIL** — Data Scientist без опыта → `assessment_decision=fail`.
   - **ALT-ACCEPT** — DS без ML-стека → альтернатива (DA) → `affirm` → `pass`.
   - **ALT-DENY** — тот же DS-кейс, но `deny` → `utter_goodbye_after_decline`.
   - **RESTART** — сброс посередине формы (`restart_interview` → `action_reset_interview`).
   - **OOS-IN-FORM** — `out_of_scope` внутри формы → `utter_please_continue_form` → форма продолжается.
2. **`tests/test_actions.py`** — pytest-юниты на helper'ы `actions.actions`:
   `_parse_salary` (8 валидных + 5 невалидных кейсов), `_normalize_skills`,
   `EMAIL_RE` (4 + 6 кейсов), `_split_skills`, `_load_roles`, и три сценария
   `_run_assessment` (pass / fail / alternative + неизвестная роль). Всего
   32 теста.

### Куда складываются результаты

- `rasa test` → JSON-отчёты и confusion matrices в `results/` (директория
  игнорируется в `.gitignore`). Если какая-то история провалилась — её
  пошаговая диагностика лежит в `results/failed_test_stories.yml`.
- `pytest` → итоговая таблица «прошёл/упал» прямо в терминале.

### Быстрый запуск из корня репозитория

```bash
cd 03_hr_bot && make test
```

Перед первым запуском не забудь обучить модель: `make train` (или `make all`,
который выполнит `validate → train → test` подряд).

## Идеи для самостоятельного задания (post-MVP)

См. DESIGN.md §10 — дорожная карта итераций. После завершения базового
скелета можно расширять:

1. Добавить роль (например, `qa_engineer`) — новые синонимы в lookup `role`,
   новая строка в `roles_requirements.csv`, обновление `domain.yml`.
2. Заменить CSV на SQLite/PostgreSQL и подключить через SQLAlchemy в action.
3. Добавить интеграцию с Telegram (через `credentials.yml`) — см. Bonus А.
4. Поднять CI на GitHub Actions: `rasa data validate` + `rasa train --dry-run`.
