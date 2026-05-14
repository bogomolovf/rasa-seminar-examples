# 03_hr_bot — HR-ассистент первичного скрининга

## Педагогическая цель

Показать **полный цикл боевого RASA-проекта на бизнес-задачу**: HR-скрининг
кандидатов на 5 ролей ML-команды (PM / DA / DE / DS / MLOps). В отличие от
`02_phones_bot` (который был «справочником с одним слотом»), здесь у нас
**многошаговая форма с per-slot валидацией, decision-action на CSV,
sad-path-сценарии и регрессионные тесты** — то, что обычно появляется уже
в продакшн-ботах.

Полная спецификация контракта диалога — в [`DESIGN.md`](DESIGN.md).

## Что нового по сравнению с `02_phones_bot`

| Концепт | Где смотреть | Что показывает |
|---|---|---|
| **Categorical slot** с `influence_conversation: true` | `domain.yml` (`desired_role`, `assessment_decision`) | Слот ветвит политику: разные ответы и разные rule'ы под `pass`/`fail`/`alternative` |
| **FormValidationAction** с per-slot методами | `actions/actions.py` (`ValidateInterviewForm`) | 5 методов `validate_<slot>`: имя, email (regex), опыт (число + «3 года»), навыки (list-нормализация), зарплата (гибкий парсер) |
| **Multi-step decision action** с CSV-таблицей правил | `actions/actions.py` (`ActionAssessCandidate`, `roles_requirements.csv`) | Сравнение слотов кандидата с требованиями ролей через stdlib `csv` (без pandas) и решение pass/fail/alternative |
| **Regex-фичи внутри DIET** + lookup combo | `data/nlu.yml` (`- regex: email`, `- regex: salary_amount`, `- lookup: skill/role`) | Извлечение email/зарплаты/опыта regex'ом БЕЗ отдельного `RegexEntityExtractor` (избегаем конфликта экстракторов из README phones-бота) |
| **Alternative-role flow** + chained re-assessment | `actions/actions.py` (`ActionOfferAlternativeRole`) | Решение `alternative` → кнопки Да/Нет → при `affirm` сразу переоцениваем кандидата под альтернативную роль (без `FollowupAction`, чтобы не словить circuit breaker) |
| **Sad-path stories** | `data/rules.yml`, `tests/test_stories.yml` | `restart_interview` внутри/вне формы, `out_of_scope` внутри активной формы, отказ от альтернативы |
| **Регрессионные тесты + Makefile** | `tests/test_stories.yml`, `tests/test_actions.py`, `Makefile` | 6 story-сценариев (`rasa test`) + 32 unit-теста на helper'ы (`pytest`), запуск одной командой `make test` |

## Сценарии диалога

Все три транскрипта ниже — реальный вывод REST-эндпоинта `/webhooks/rest/webhook`
на актуальной модели; короткие комментарии «(slot: …)» поясняют, какой слот
заполнился после каждой реплики кандидата.

### Сценарий 1 — PASS: Data Scientist с полным стеком

```
Кандидат: Хочу пройти собеседование          (intent: start_interview → запуск interview_form)
Бот:      Как тебя зовут? (имя и фамилия)

Кандидат: Иван Петров                         (entity full_name → slot candidate_name="Иван Петров")
Бот:      На какой email отправить материалы?

Кандидат: ivan@example.com                    (entity email → slot candidate_email="ivan@example.com")
Бот:      На какую роль вы претендуете?
          [Project Manager] [Data Analyst] [Data Engineer]
          [Data Scientist]  [MLOps Engineer]

Кандидат: Data Scientist                      (entity role → synonym → slot desired_role="ds")
Бот:      Сколько лет опыта работы в IT/ML у тебя? (число)

Кандидат: 5 лет                               (entity years_experience="5" → slot 5.0)
Бот:      Перечисли ключевые навыки через запятую (Python, SQL, ML-фреймворки и т.п.).

Кандидат: Python, scikit-learn, PyTorch       (3× entity skill → slot skills=["python","scikit-learn","pytorch"])
Бот:      Какую зарплату ты ожидаешь? Можно числом (например, 200000), словом (200к, 200 тысяч) или с валютой (300 000 ₽).

Кандидат: 200000                              (entity salary_amount → slot expected_salary=200000.0)
Бот:      Иван Петров, отлично — ты подходишь на роль ds. Свяжемся для следующего этапа.
                                              (action_assess_candidate → SlotSet assessment_decision="pass")
```

### Сценарий 2 — FAIL: DS без опыта

```
Кандидат: начать                              (intent: start_interview)
Бот:      Как тебя зовут? (имя и фамилия)
Кандидат: Мария Иванова                       (slot candidate_name="Мария Иванова")
Бот:      На какой email отправить материалы?
Кандидат: maria@example.com                   (slot candidate_email="maria@example.com")
Бот:      На какую роль вы претендуете? […кнопки…]
Кандидат: /inform{"role":"ds"}                (button payload → slot desired_role="ds")
Бот:      Сколько лет опыта…
Кандидат: 0                                   (slot years_experience=0.0)
Бот:      Перечисли ключевые навыки…
Кандидат: Python                              (slot skills=["python"])
Бот:      Какую зарплату ты ожидаешь?…
Кандидат: 180000                              (slot expected_salary=180000.0)
Бот:      К сожалению, по итогам сегодня не подходим.
Бот:      Нужно ≥ 2 лет опыта; у тебя 0.
                                              (action_assess_candidate → SlotSet assessment_decision="fail")
```

> Решение `fail` побеждает даже если навыки в порядке: `years_experience < min_years`
> блокирует и pass, и alternative-ветку (см. `_run_assessment` в `actions/actions.py`).

### Сценарий 3 — ALTERNATIVE-ACCEPT: DS без ML-стека → Data Analyst

```
Кандидат: начать
…
Кандидат: Сергей Морозов                      (slot candidate_name)
Кандидат: sergey@example.com                  (slot candidate_email)
Кандидат: /inform{"role":"ds"}                (slot desired_role="ds")
Кандидат: 5                                   (slot years_experience=5.0  — опыта хватает)
Кандидат: SQL, Python, Tableau                (slot skills=["sql","python","tableau"]  — но НЕТ ML-стека для DS)
Кандидат: 150000                              (slot expected_salary=150000.0)
Бот:      По исходной роли ds не проходишь, но есть подходящая альтернатива: Data Analyst.
Бот:      Не хватает обязательных навыков: pytorch, scikit-learn.
Бот:      Хочешь обсудить роль Data Analyst? Да/Нет
          [Да] [Нет]
                                              (action_assess_candidate → SlotSet assessment_decision="alternative",
                                               alternative_role_name="Data Analyst")

Кандидат: Да                                  (intent: affirm)
Бот:      Хорошо, теперь рассматриваем тебя как Data Analyst.
Бот:      Сергей Морозов, отлично — ты подходишь на роль da. Свяжемся для следующего этапа.
                                              (action_offer_alternative_role → SlotSet desired_role="da",
                                               затем _run_assessment(...) → SlotSet assessment_decision="pass")
```

> Если на той же точке кандидат отвечает «Нет» (`intent: deny`), срабатывает
> rule «Отказ от альтернативы» → `utter_goodbye_after_decline`
> («Хорошо, спасибо за уделённое время. Удачи!»).

## База `roles_requirements.csv`

CSV из 5 строк (одна на роль) живёт в корне примера. Колонки:

| Колонка | Тип | Назначение |
|---|---|---|
| `role` | str (`pm`/`da`/`de`/`ds`/`mlops`) | Канонический код, совпадает со значениями слота `desired_role` |
| `role_name` | str | Человекочитаемое имя для шаблонов («Data Analyst») |
| `min_years` | int | Минимальный требуемый опыт (`years_experience >= min_years`) |
| `required_skills` | str (`;`-разделитель) | Навыки, которые **должны быть все** (`set ⊆ candidate_skills`) |
| `nice_to_have_skills` | str (`;`-разделитель) | Информативно, не влияет на решение |
| `salary_min` / `salary_max` | int | Диапазон бюджета. Превышение `salary_max` — warning, не fail |
| `alternative_role` | str (`pm`/…) или пусто | Куда направить кандидата, если не хватает required_skills |

### Логика ассессмента (см. `_run_assessment` в `actions/actions.py`)

1. `match_years = years_experience >= min_years`
2. `match_required = set(required_skills) ⊆ set(candidate_skills)` (case-insensitive; пустой required → True, как у PM)
3. Решение:
   - `match_required AND match_years` → **pass**
   - `match_years AND NOT match_required AND alternative_role` → **alternative**
   - иначе (`NOT match_years` ИЛИ нет `alternative_role`) → **fail**

> Опыт «перевешивает» навыки: даже если стек идеальный, но `years_experience <
> min_years`, мы не предлагаем альтернативу, а сразу `fail`. Это сознательный
> выбор HR-логики: junior-кандидата не имеет смысла перекидывать на роль с тем
> же требованием по стажу.

### Как добавить новую роль

1. Добавить строку в `roles_requirements.csv`, например:
   ```csv
   qa,QA Engineer,1,python;selenium,pytest;allure;jenkins,90000,160000,da
   ```
2. Расширить `values:` слота `desired_role` в `domain.yml`:
   ```yaml
   desired_role:
     type: categorical
     values: [pm, da, de, ds, mlops, qa]
   ```
3. Добавить кнопку в `utter_ask_desired_role` (`payload: '/inform{"role":"qa"}'`).
4. Добавить синонимы в `data/nlu.yml`:
   - в `- lookup: role` строки `qa`, `QA`, `qa engineer`, `тестировщик`, …
   - блок `- synonym: qa` со всеми вариантами.
5. (Опционально) добавить новые навыки (`selenium`, `pytest`) в `- lookup: skill`.
6. `make validate && make train` — проверить, что обучение проходит.

## Команды запуска

```bash
# 1. Перейти в директорию примера
cd 03_hr_bot

# 2. Обучить модель + прогнать тесты + валидацию (см. Makefile)
make all                         # validate → train → test
# или по отдельности:
make validate                    # rasa data validate
make train                       # rasa train --quiet
make test                        # rasa test (stories) + pytest (unit)

# 3. В отдельном терминале — action server (порт 5055)
/Users/fedorbogomolov/Desktop/examples/.venv/bin/rasa run actions

# 4. В основном терминале — REST API (порт 5005)
/Users/fedorbogomolov/Desktop/examples/.venv/bin/rasa run --enable-api --cors "*" -p 5005
```

> **Зачем абсолютный путь к `rasa`?** Conda prefix-env `./.venv` создан через
> `conda create -p ./.venv …` и **не имеет** `bin/activate`-скрипта. См.
> `CLAUDE.md` корня и `SETUP_ANACONDA.md`. `Makefile` уже использует
> абсолютный путь.

### Примеры curl-запросов на `/webhooks/rest/webhook`

Все три сценария ниже — реальные транскрипты против запущенного локально
сервера. Один и тот же `sender` сохраняет состояние и слоты между запросами;
для сброса — отправь `/restart` (встроенный intent RASA).

**Happy path 1 — PASS (роль DS, полный стек):**

```bash
SENDER=pass_demo
curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d "{\"sender\":\"$SENDER\",\"message\":\"Хочу пройти собеседование\"}"
# → "Как тебя зовут? (имя и фамилия)"

curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d "{\"sender\":\"$SENDER\",\"message\":\"Иван Петров\"}"
# → "На какой email отправить материалы?"

curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d "{\"sender\":\"$SENDER\",\"message\":\"ivan@example.com\"}"
# → "На какую роль вы претендуете?" + 5 кнопок

curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d "{\"sender\":\"$SENDER\",\"message\":\"Data Scientist\"}"
# → "Сколько лет опыта работы в IT/ML у тебя? (число)"

curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d "{\"sender\":\"$SENDER\",\"message\":\"5 лет\"}"
# → "Перечисли ключевые навыки через запятую…"

curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d "{\"sender\":\"$SENDER\",\"message\":\"Python, scikit-learn, PyTorch\"}"
# → "Какую зарплату ты ожидаешь?…"

curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d "{\"sender\":\"$SENDER\",\"message\":\"200000\"}"
# → "Иван Петров, отлично — ты подходишь на роль ds. Свяжемся для следующего этапа."
```

**Happy path 2 — FAIL (DS без опыта):**

```bash
SENDER=fail_demo
# (повторяем тот же sequence до слота "skills" с другими значениями)
curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d "{\"sender\":\"$SENDER\",\"message\":\"180000\"}"
# → "К сожалению, по итогам сегодня не подходим."
# → "Нужно ≥ 2 лет опыта; у тебя 0."
```

**Happy path 3 — ALTERNATIVE accept (DS → DA):**

```bash
SENDER=alt_demo
# (заполняем форму как DS с опытом 5 лет, но без ML-навыков: SQL, Python, Tableau)
curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d "{\"sender\":\"$SENDER\",\"message\":\"150000\"}"
# → "По исходной роли ds не проходишь, но есть подходящая альтернатива: Data Analyst."
# → "Не хватает обязательных навыков: pytorch, scikit-learn."
# → "Хочешь обсудить роль Data Analyst? Да/Нет" + кнопки

curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d "{\"sender\":\"$SENDER\",\"message\":\"Да\"}"
# → "Хорошо, теперь рассматриваем тебя как Data Analyst."
# → "Сергей Морозов, отлично — ты подходишь на роль da. Свяжемся для следующего этапа."
```

**Проверка только NLU (без диалога):**

```bash
curl -s -X POST http://localhost:5005/model/parse \
     -H "Content-Type: application/json" \
     -d '{"text": "Я data scientist с 5 годами опыта"}'
# → intent: inform (1.0); entities:
#   - role="ds" (extractor=DIETClassifier, processors=[EntitySynonymMapper])
#   - years_experience="5"
```

## Структура файлов

```
03_hr_bot/
├── DESIGN.md                  # спецификация контракта диалога (intents/entities/slots/actions/CSV)
├── README.md                  # этот файл
├── Makefile                   # train / validate / test / clean / all (использует ./.venv/bin/rasa напрямую)
├── config.yml                 # pipeline (DIET + EntitySynonymMapper + FallbackClassifier) + policies (Memo+Rule+TED)
├── domain.yml                 # 9 intents, 6 entities, 7 slots, 1 form, 4 actions, 14 responses
├── endpoints.yml              # action_endpoint: http://localhost:5055/webhook
├── roles_requirements.csv     # 5 ролей × 8 колонок (правила ассессмента)
├── data/
│   ├── nlu.yml                # 9 intents + 3 regex-фичи (email/years/salary) + 2 lookup (role/skill) + synonyms
│   ├── rules.yml              # 9 rules (greet, goodbye, oos, bot_challenge, форма, alternative, restart×2)
│   └── stories.yml            # 2–3 happy-path истории для TEDPolicy
├── actions/
│   ├── __init__.py
│   └── actions.py             # 4 класса: ActionResetInterview, ActionAssessCandidate,
│                              # ActionOfferAlternativeRole, ValidateInterviewForm
│                              # + helper'ы: _parse_salary, _normalize_skills, _load_roles, _split_skills, _run_assessment
└── tests/
    ├── __init__.py
    ├── test_stories.yml       # 6 regression-stories: pass / fail / alt-accept / alt-deny / restart / oos-in-form
    └── test_actions.py        # 32 pytest-юнита на helper'ы (parser'ы, regex, ассессмент)
```

> Игнорятся (см. корневой `.gitignore`): `models/`, `.rasa/`, `results/`,
> `__pycache__/`, `*.tar.gz`. Перед коммитом локально удаляются через
> `make clean` (или `rm -rf models .rasa results`).

## Тесты

`make test` запускает обе группы:

1. **`tests/test_stories.yml`** — `rasa test --stories tests/test_stories.yml --out results/`.
   6 сценариев: 3 happy (`pass`/`fail`/`alt-accept`) + 3 sad (`alt-deny`/`restart`/`oos-in-form`).
   Отчёты — JSON + confusion matrices в `results/`; провалившиеся сторис — в
   `results/failed_test_stories.yml`.
2. **`tests/test_actions.py`** — `pytest tests/`. 32 юнит-теста на helper'ы:
   `_parse_salary` (8 валидных + 5 невалидных кейсов), `_normalize_skills`,
   `EMAIL_RE` (4 + 6), `_split_skills`, `_load_roles`, и `_run_assessment`
   (pass/fail/alternative + неизвестная роль).

Перед первым запуском — `make train` (или `make all` = validate → train → test).

## Чек-лист при отладке «бот ведёт себя не так»

1. **NLU не извлёк `role`/`skill`/`email`?** → `POST /model/parse` с проблемным текстом.
   Проверь, что значение есть в `- lookup: role` (или `skill`) и что synonym-блок
   приводит его к каноническому коду (`pm`/`da`/`de`/`ds`/`mlops`). Для `email`/
   `salary_amount`/`years_experience` — проверь, что `- regex: <name>` в `nlu.yml`
   матчит ввод (`python -c "import re; print(re.findall(r'<pattern>', '<text>'))"`).
2. **Несколько entities от разных extractor'ов на одно вхождение?** Тот же конфликт,
   что и в README phones-бота. Мы НЕ подключаем `RegexEntityExtractor` отдельно —
   regex используется только как **фича внутри DIET** (`- regex: email` в `nlu.yml`).
   Если у тебя есть и `DIETClassifier`, и `RegexEntityExtractor` для одной сущности —
   убирай второй.
3. **`FormValidationAction` не вызывается?** Проверь:
   - объявлена ли в `domain.yml → actions:` строка `- validate_interview_form`
     (имя метода = `name()` action'а);
   - запущен ли action server (`lsof -i:5055`);
   - в логах `rasa run actions` есть ли строка `Registered function for
     'validate_interview_form'`;
   - имя метода — точно `validate_<slot_name>` (snake_case того же слота из формы).
4. **Action возвращает `SlotSet`, но слот не меняется?** Скорее всего `mappings`
   слота не содержит `type: custom` (по умолчанию RASA пытается применить
   автоматическое заполнение из сообщения **после** твоего SlotSet и затирает
   его). Для слотов вроде `assessment_decision` обязательно `mappings: [{type:
   custom}]`.
5. **`assessment_decision` не выставился после формы?** Проверь rule «Завершение
   interview_form — ассессмент кандидата» в `data/rules.yml`: в нём должно быть
   `active_loop: null` + `slot_was_set: requested_slot: null` + `action:
   action_assess_candidate`. Без этих маркеров RulePolicy не понимает «форма
   завершилась» и уходит в core_fallback.
6. **`restart_interview` не срабатывает внутри формы?** RASA по умолчанию внутри
   активной формы переспрашивает текущий слот и игнорирует другие intents.
   Решение — две rule'ы (внутри формы и вне) + `not_intent` в `mappings.from_text`
   соответствующего слота (см. `domain.yml` → `candidate_name.mappings.not_intent`),
   иначе `from_text` затягивает «давай заново» в имя/email и rule не триггерится.
7. **`Contradicting rules` при обучении?** Чаще всего — два rule с одинаковыми
   `intent` без условия по `slot_was_set`/`active_loop`. Например, intent
   `affirm` после формы должен быть условно по `assessment_decision: alternative`,
   иначе он конфликтует с happy-path подтверждением старта интервью.
8. **`Circuit breaker tripped` после `FollowupAction`?** Видели в Промпте 7: rule
   запускает action, тот делает `FollowupAction(...)`, который снова триггерит
   что-то — RulePolicy уходит в бесконечный цикл. Решение в нашем коде —
   `ActionOfferAlternativeRole` НЕ возвращает `FollowupAction`, а сам зовёт
   `_run_assessment(...)` синхронно (см. комментарий в `actions.py`).
9. **`message did not contain entity` для слота из `from_text`?** В `domain.yml`
   проверь `mappings.conditions` слота: должны быть `active_loop:
   interview_form` И `requested_slot: <slot_name>`. Без condition'ов `from_text`
   срабатывает на любом сообщении и съедает чужой ввод.

## Идеи для самостоятельного задания

1. **Добавить роль `qa_engineer`** — новая строка в `roles_requirements.csv`,
   расширить `values:` слота `desired_role`, добавить кнопку, синонимы и lookup
   в `nlu.yml` (см. инструкцию в разделе «База `roles_requirements.csv`» выше).
2. **Добавить слот `current_employer`** (`type: text`) — новый required_slot в
   `interview_form`, `utter_ask_current_employer`, валидатор `validate_current_employer`
   (минимум 2 символа). Использовать в финальном сообщении ассессмента
   («…переходишь из <employer>»).
3. **Добавить test_actions case** для нового алгоритма ассессмента: например,
   расширить `_run_assessment` так, чтобы при `over_salary` и pass — добавлялся
   warning, и проверить это юнит-тестом на `dispatcher.messages`.
4. **Поднять Telegram-канал** — `credentials.yml` с секцией `telegram:` (см.
   [docs](https://rasa.com/docs/rasa/connectors/telegram/)), запуск через
   `rasa run -p 5005 --credentials credentials.yml`. **Не коммитить токен!**
5. **A/B сравнение pipelines** — взять текущий `config.yml` и `config-no-ted.yml`
   (только Memo + Rule), прогнать `rasa test` на обоих и сравнить F1 по intent'ам
   и success rate по сторис в `results/`. Какой даёт лучший recall на sad-path?
