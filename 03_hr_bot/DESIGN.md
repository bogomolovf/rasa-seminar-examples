# 03_hr_bot — DESIGN.md

Дизайн-документ HR-бота: первичный скрининг кандидатов на 5 ролей ML-команды
(**pm**, **da**, **de**, **ds**, **mlops**). Документ описывает контракт диалога —
интенты, сущности, слоты, форму, custom actions, схему данных и pipeline —
который будет реализован в следующих итерациях.

Бот говорит **по-русски**. Идентификаторы (intent/entity/slot/action) — **английский
snake_case**, как в `02_phones_bot`.

---

## 1. Сценарий MVP (happy path, роль Data Scientist)

Диалог из ~10 реплик, который должен пройти из коробки после реализации всех итераций:

```
1. Кандидат:  Привет
2. Бот:       Привет! Я HR-ассистент команды ML. Помогу пройти первичный скрининг
              на одну из 5 ролей. Хотите начать собеседование?
3. Кандидат:  Да, давайте
4. Бот:       Отлично. На какую роль вы претендуете?
              [Project Manager] [Data Analyst] [Data Engineer]
              [Data Scientist]  [MLOps Engineer]
5. Кандидат:  Data Scientist
6. Бот:       Записал: Data Scientist. Как вас зовут?
7. Кандидат:  Иван Петров
8. Бот:       Приятно познакомиться, Иван. Оставьте, пожалуйста, ваш email
              для обратной связи.
9. Кандидат:  ivan.petrov@example.com
10. Бот:      Сколько лет коммерческого опыта в ML/Data Science?
11. Кандидат: 3 года
12. Бот:      Перечислите ключевые навыки через запятую (Python, PyTorch и т.д.).
13. Кандидат: Python, scikit-learn, PyTorch, pandas
14. Бот:      На какую зарплату рассчитываете (₽/мес)?
15. Кандидат: 220000
16. Бот:      Спасибо! Проверяю соответствие требованиям…
              ✅ Решение: PASS. Вы подходите на роль Data Scientist.
              Опыт: 3 года (мин. 2). Навыки: Python, scikit-learn, PyTorch (3 из 3
              обязательных). Зарплата 220 000 ₽ в диапазоне 150 000–300 000 ₽.
              С вами свяжется рекрутёр по адресу ivan.petrov@example.com.
17. Кандидат: Спасибо, пока
18. Бот:      Удачи, Иван! До свидания.
```

> Реплик кандидата ровно 9, бота — 9. Это «золотая» история, которой будет
> соответствовать одна story в `data/stories.yml` и smoke-curl в `Makefile`.

---

## 2. Sad-path сценарии

### 2.1. Пользователь отказывается отвечать в форме

```
Бот:       Как вас зовут?
Кандидат:  Не хочу говорить
Бот:       Понимаю. Без имени продолжить скрининг не получится — оно нужно
           рекрутёру. Назовите имя или скажите «начать заново», чтобы прервать.
Кандидат:  Начать заново
Бот:       Хорошо, сбрасываю собеседование. Когда будете готовы — напишите «начать».
```

Реализация: интент `deny` внутри формы → `utter_explain_why_needed` + повторный
вопрос; интент `restart` → `action_reset_interview`.

### 2.2. Не подходит ни под одну роль

```
Кандидат:  Хочу собеседоваться на бэкенд-разработчика
Бот:       Я провожу скрининг только на 5 ролей ML-команды: PM, DA, DE, DS, MLOps.
           Выберите подходящую или скажите «пока».
           [Project Manager] [Data Analyst] [Data Engineer]
           [Data Scientist]  [MLOps Engineer]
```

Реализация: `validate_interview_form` на слоте `desired_role` отклоняет
значение вне списка `pm/da/de/ds/mlops` и возвращает `utter_ask_desired_role`.

После прогона формы с DS-кандидатом без ML-навыков:

```
Бот:       ⚠️ Решение: ALTERNATIVE. На DS не подходите — нет обязательных
           навыков (Python, scikit-learn, PyTorch). Рассмотрите Data Analyst:
           ваш SQL-опыт и аналитический бэкграунд подойдут. Согласны?
```

### 2.3. Out-of-scope запрос

```
Кандидат:  Какая погода в Москве?
Бот:       Я провожу только HR-скрининг на ML-роли. Напишите «начать»,
           чтобы перейти к интервью, или «пока» — чтобы закончить.
```

Реализация: интент `out_of_scope` + `FallbackClassifier` (threshold 0.7) →
`utter_out_of_scope`.

---

## 3. Intents

Всего **11 интентов** (лимит ≤ 12 соблюдён).

| Intent           | Описание                                             | Примеры (ru)                                                              |
| ---------------- | ---------------------------------------------------- | ------------------------------------------------------------------------- |
| `greet`          | Приветствие                                          | «Привет», «Здравствуйте», «Добрый день»                                  |
| `goodbye`        | Прощание                                             | «Пока», «До свидания», «Спасибо, на этом всё»                            |
| `start_interview`| Готов начать собеседование                          | «Хочу пройти собеседование», «Давай начнём», «Готов к интервью»          |
| `inform`         | Свободный ответ (имя/email/опыт/навыки/зарплата/роль)| «Иван Петров», «ivan@example.com», «3 года», «Python, PyTorch», «220000»|
| `affirm`         | Подтверждение                                        | «Да», «Согласен», «Конечно»                                              |
| `deny`           | Отказ                                                | «Нет», «Не хочу отвечать», «Пропусти»                                    |
| `ask_about_role` | Вопрос про роль/требования                          | «Что делает Data Scientist?», «Какие требования к MLOps?», «Расскажи про DA»|
| `restart`        | Сбросить состояние и начать заново                  | «Начать заново», «Сброс», «Перезапусти интервью»                         |
| `bot_challenge`  | «Ты бот?»                                            | «Ты человек?», «Это бот?», «Кто ты?»                                     |
| `out_of_scope`   | Запрос вне области HR-скрининга                      | «Какая погода?», «Расскажи анекдот», «Реши задачу»                       |
| `thank`          | Благодарность (мягкое завершение)                    | «Спасибо», «Благодарю», «Отлично, спасибо»                              |

> `inform` намеренно один общий — слот определяется по контексту формы
> (`requested_slot`) и mapping'ам сущностей, как в `02_phones_bot`.

---

## 4. Entities

| Entity           | Способ извлечения              | Куда мапится / где используется                                |
| ---------------- | ------------------------------ | -------------------------------------------------------------- |
| `role`           | DIET + `lookup table` + `synonym` | → слот `desired_role` (mapping `from_entity`); канонизация через synonyms (`датасаентист` → `ds`) |
| `years_experience` | Regex `\b\d{1,2}\b` (число лет) | → слот `years_experience` (`from_entity`)                      |
| `skill`          | DIET + `lookup table` (Python, SQL, Spark, …) | накапливается в слот `skills` (list) через `from_entity` + custom validation |
| `salary_amount`  | Regex `\b\d{2,3}[\s_]?\d{3}\b|\b\d{2,3}\s?(?:k|к|тыс|т)\b|\b\d{6}\b` | → слот `expected_salary` (нормализуется в validate-action к float) |
| `email`          | Regex `[\w.+-]+@[\w-]+\.[\w.-]+`| → слот `candidate_email`                                       |
| `full_name`      | DIET (без lookup; учим на примерах «Иван Петров», «Анна Смирнова» …) | → слот `candidate_name`                                        |

> Lookup table `role`: `pm`, `project manager`, `проджект`, `da`, `data analyst`,
> `аналитик данных`, `de`, `data engineer`, `дата инженер`, `ds`, `data scientist`,
> `датасаентист`, `mlops`, `mlops engineer`, `млопс`. Synonyms приводят к
> 5 каноническим значениям `pm/da/de/ds/mlops`.

> Lookup table `skill` (≈ 25 значений): `Python, SQL, Tableau, Power BI, Excel,
> Spark, Airflow, Kafka, Hadoop, Hive, scikit-learn, PyTorch, TensorFlow, pandas,
> NumPy, XGBoost, LightGBM, Docker, Kubernetes, MLflow, Kubeflow, Git, AWS, GCP,
> Linux, Bash, Agile, Scrum, Jira`.

---

## 5. Slots

| Slot                  | Type        | `influence_conversation` | Mapping (одна строка)                                                                    |
| --------------------- | ----------- | ------------------------ | ---------------------------------------------------------------------------------------- |
| `candidate_name`      | text        | false                    | `from_entity: full_name` + `from_text` (intent: `inform`, `requested_slot: candidate_name`) |
| `candidate_email`     | text        | false                    | `from_entity: email` + `from_text` (intent: `inform`, `requested_slot: candidate_email`) |
| `desired_role`        | categorical | true                     | `from_entity: role` (values: `pm, da, de, ds, mlops`)                                    |
| `years_experience`    | float       | false                    | `from_entity: years_experience` + `from_text` (intent: `inform`, `requested_slot`)       |
| `skills`              | list        | false                    | `from_entity: skill` (накапливается); валидатор парсит CSV-строку из `from_text`         |
| `expected_salary`     | float       | false                    | `from_entity: salary_amount` + `from_text` (нормализация в `validate_interview_form`)    |
| `assessment_decision` | categorical | true                     | `custom` — выставляется `action_assess_candidate` (values: `pass, fail, alternative`)    |

> `influence_conversation: true` стоит только на тех слотах, по значению которых
> ветвится дальнейшее поведение (`desired_role` → разные ветви валидации,
> `assessment_decision` → разные ответы в конце).

---

## 6. Form `interview_form`

`required_slots` (порядок строгий — определяет последовательность вопросов):

1. `desired_role`
2. `candidate_name`
3. `candidate_email`
4. `years_experience`
5. `skills`
6. `expected_salary`

После заполнения всех 6 слотов форма деактивируется и вызывается
`action_assess_candidate`.

`utter_ask_<slot>` (по одной формулировке на каждый):

| Slot                | `utter_ask_<slot>`                                                                              |
| ------------------- | ----------------------------------------------------------------------------------------------- |
| `desired_role`      | «На какую роль вы претендуете?» **+ 5 кнопок** (payload `/inform{"role":"<code>"}`)             |
| `candidate_name`    | «Как вас зовут? Назовите имя и фамилию.»                                                        |
| `candidate_email`   | «Оставьте, пожалуйста, ваш email для обратной связи.»                                           |
| `years_experience`  | «Сколько лет коммерческого опыта по выбранной роли?»                                            |
| `skills`            | «Перечислите ключевые навыки через запятую (например: Python, SQL, Airflow).»                  |
| `expected_salary`   | «На какую зарплату рассчитываете (₽/мес)? Можно числом или вида «250к».»                       |

Кнопки для `desired_role`:
```
- title: "Project Manager",   payload: '/inform{"role":"pm"}'
- title: "Data Analyst",      payload: '/inform{"role":"da"}'
- title: "Data Engineer",     payload: '/inform{"role":"de"}'
- title: "Data Scientist",    payload: '/inform{"role":"ds"}'
- title: "MLOps Engineer",    payload: '/inform{"role":"mlops"}'
```

---

## 7. Custom actions

### 7.1. `validate_interview_form` (FormValidationAction)

Per-slot валидация. Базовая логика на каждый слот:

| Слот               | Что проверяет                                                                                          | На неуспех                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| `desired_role`     | значение из `{pm, da, de, ds, mlops}` после канонизации synonyms                                        | `utter_role_not_recognized` + слот в `None` (форма переспросит)                             |
| `candidate_name`   | `len(name) >= 2`, нет цифр, кириллица или латиница, минимум 1 пробел (имя + фамилия — soft warning)    | `utter_name_invalid`                                                                        |
| `candidate_email`  | regex `^[\w.+-]+@[\w-]+\.[\w.-]+$`                                                                     | `utter_email_invalid`                                                                       |
| `years_experience` | float ≥ 0 и ≤ 40; парсит «3», «3 года», «3.5», «полтора» (через словарь) → float                       | `utter_experience_invalid`                                                                  |
| `skills`           | парсит CSV-строку, нормализует к lookup-словарю (case-insensitive), фильтрует пустые; ≥ 1 навык        | `utter_skills_invalid`                                                                      |
| `expected_salary`  | parsing: убирает пробелы/`_`, поддерживает `k/к/тыс` (`250к` → 250000), `200000`, диапазон `200-250` → берёт нижнюю границу; > 0 и < 1000000 | `utter_salary_invalid` |

### 7.2. `action_assess_candidate`

Логика:
1. Загружает `roles_requirements.csv` (pandas, как в `02_phones_bot`).
2. Берёт строку по `desired_role`.
3. Сравнивает со слотами:
   - `years_experience >= min_years`
   - `set(skills) ⊇ set(required_skills)` (case-insensitive, минимум 2 обязательных навыка)
   - `salary_min <= expected_salary <= salary_max` (нарушение — warning, не fail)
4. Решение:
   - **pass** — опыт ОК **И** все required_skills есть.
   - **alternative** — опыт ОК, но required_skills < 2 из списка; если `alternative_role` непуст в CSV — предлагаем её.
   - **fail** — опыт меньше минимального **ИЛИ** нет alternative_role.
5. Выставляет `SlotSet("assessment_decision", <pass|fail|alternative>)`, диспатчит фидбек с цифрами (опыт, найденные/недостающие навыки, диапазон зарплат).

### 7.3. `action_offer_alternative_role`

Триггерится при `assessment_decision == alternative` (через rule).
Берёт `alternative_role` из CSV для текущего `desired_role`, формирует текст:
«Рассмотрите роль <role_name>: ваши навыки <…> подходят. Согласны перейти?»
Если кандидат подтверждает (`affirm`) — переустанавливает `desired_role` на
альтернативу и заново вызывает `action_assess_candidate`. Если `deny` —
прощается через `utter_goodbye_alternative`.

### 7.4. `action_reset_interview`

Триггерится по интенту `restart`. Возвращает события:
```
SlotSet("candidate_name", None),
SlotSet("candidate_email", None),
SlotSet("desired_role", None),
SlotSet("years_experience", None),
SlotSet("skills", None),
SlotSet("expected_salary", None),
SlotSet("assessment_decision", None),
ActiveLoop(None),
FollowupAction("utter_restart_done"),
```

---

## 8. `roles_requirements.csv`

Схема (header):
```
role,role_name,min_years,required_skills,nice_to_have_skills,salary_min,salary_max,alternative_role
```

Разделитель колонок — `,`; внутри `required_skills` / `nice_to_have_skills` —
`;`. Строки заворачиваются в `"..."`, потому что внутри есть запятые
русских названий.

Готовые данные на 5 ролей:

```csv
role,role_name,min_years,required_skills,nice_to_have_skills,salary_min,salary_max,alternative_role
pm,"Project Manager",2,"Agile;Scrum;Jira","Power BI;Excel;SQL",120000,250000,
da,"Data Analyst",1,"SQL;Python;Tableau","Power BI;Excel;pandas",100000,180000,pm
de,"Data Engineer",2,"Spark;Airflow;Kafka","Hadoop;Hive;Docker;SQL",150000,280000,da
ds,"Data Scientist",2,"Python;scikit-learn;PyTorch","pandas;NumPy;XGBoost;LightGBM;SQL",150000,300000,da
mlops,"MLOps Engineer",3,"Docker;Kubernetes;MLflow","Kubeflow;AWS;GCP;Airflow;Git",180000,320000,de
```

Все цифры — реальные дефолты (без TODO). Источник: рыночные ставки Москвы 2025
для middle-уровня (HH, Habr Career). Альтернативы:
- `pm` → пусто (PM — нетехническая роль, downgrade в DA/DE/DS не имеет смысла).
- `da` → `pm` (аналитики часто переходят в продукт/проект-менеджмент).
- `de` → `da` (downgrade по инженерной сложности, SQL и pipeline-опыт пригодятся).
- `ds` → `da` (классический downgrade при отсутствии ML-стека).
- `mlops` → `de` (если нет Docker/K8s/MLflow, но есть Spark/Airflow — это DE).

> DS-кандидат с инженерным уклоном (есть Spark/Airflow) теоретически мог бы
> предложить DE-альтернативу, но усложнять CSV на MVP не будем — один
> `alternative_role` на строку, выбор в `action_offer_alternative_role`
> детерминированный.

---

## 9. Pipeline / policies

Берём `02_phones_bot/config.yml` **as is**, меняем только `assistant_id`
(он генерируется RASA автоматически при первом обучении).

```yaml
recipe: default.v1
language: ru

pipeline:
- name: WhitespaceTokenizer
- name: CountVectorsFeaturizer
  analyzer: char_wb
  min_ngram: 2
  max_ngram: 4
- name: CountVectorsFeaturizer
  analyzer: word
- name: DIETClassifier
  epochs: 100
  constrain_similarities: true
- name: EntitySynonymMapper
- name: FallbackClassifier
  threshold: 0.7
  ambiguity_threshold: 0.1

policies:
- name: MemoizationPolicy
  max_history: 5
- name: RulePolicy
  core_fallback_threshold: 0.4
  core_fallback_action_name: utter_out_of_scope
- name: TEDPolicy
  max_history: 5
  epochs: 100
```

**Что меняем:** ничего, кроме автогенерируемого `assistant_id`.

**Почему то же подходит:** DIET закрывает классификацию интентов + извлечение
сущностей (включая `role`/`skill` через lookup, `full_name` через примеры).
`EntitySynonymMapper` нормализует синонимы роли в `pm/da/de/ds/mlops`.
`RulePolicy` обслуживает rule-based ветки (`restart`, `out_of_scope`,
форму, `action_offer_alternative_role`). `TEDPolicy` подхватит story
happy-path и редкие отклонения (например, повтор вопроса после отказа).

> Regex для `email` и `salary_amount` мы заводим **только через regex-фичу
> внутри DIET** (`- regex: email`, `- regex: salary_amount` в `nlu.yml`),
> без отдельного `RegexEntityExtractor` — иначе будет конфликт двух
> экстракторов, как описано в README phones-бота.

---

## 10. Дорожная карта

7 крупных итераций + 3 завершающих:

1. **Скелет проекта** — `rasa init`-стиль: `config.yml`, пустые `domain.yml`,
   `data/nlu.yml`, `data/stories.yml`, `data/rules.yml`, `actions/actions.py`,
   `roles_requirements.csv` с готовыми данными.
   → `feat(hr-bot): scaffold project skeleton` — ✅ реализован
2. **Слот `desired_role` с кнопками** — intent `start_interview`, entity `role`
   + lookup + synonyms, slot categorical, форма с одним required slot, кнопки.
   → `feat(hr-bot): collect desired_role via buttons and free text` — ✅ реализован
3. **Имя + email + валидация формы** — entity `full_name`, `email` (regex
   через DIET), slots `candidate_name`/`candidate_email`,
   `validate_interview_form` (skeleton), `utter_*_invalid`.
   → `feat(hr-bot): collect candidate name and email with form validation` — ✅ реализован
4. **Опыт + навыки** — entity `years_experience` (regex), `skill` (lookup),
   slot `years_experience` (float) и `skills` (list), валидаторы.
   → `feat(hr-bot): collect years_experience and skills`
5. **Зарплата с гибким парсером** — entity `salary_amount` (regex для
   `200000`, `200к`, `250 000`, `200-250к`), валидатор-нормализатор → float.
   → `feat(hr-bot): collect expected_salary with flexible parser`
6. **Assessment engine + альтернативная роль** — `roles_requirements.csv`,
   `action_assess_candidate`, `action_offer_alternative_role`, slot
   `assessment_decision`, rules для трёх веток (pass/fail/alternative).
   → `feat(hr-bot): add assessment engine and alternative role flow`
7. **Sad-paths** — intents `restart`/`out_of_scope`/`deny`/`bot_challenge`,
   `action_reset_interview`, rules + stories для отказов и сбросов.
   → `feat(hr-bot): handle restart, deny and out_of_scope flows`
8. **Тесты** — `tests/test_stories.yml` с happy-path и тремя sad-path,
   `Makefile` с `train/test/smoke`, smoke-curl скрипт.
   → `test(hr-bot): add story tests and smoke targets`
9. **README** — описание сценариев, схема CSV, инструкция запуска (с поправкой
   на `./.venv/bin/rasa`), таблица интентов/слотов, ссылка на `DESIGN.md`.
   → `docs(hr-bot): add README with run instructions and design overview`
10. **PR `feat/hr-bot` → `main`** — финальный `PR_BODY.md`, чек-лист
    test plan, ссылка на `DESIGN.md` и Conventional-история коммитов.
    → `chore(hr-bot): finalize PR body and open pull request`

После каждой итерации — `/rasa-check` (валидация + короткое обучение),
затем `/ship feat: ...` по правилу из `CLAUDE.md`.
