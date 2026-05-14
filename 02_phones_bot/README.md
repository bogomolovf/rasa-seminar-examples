# 02_phones_bot — Бот-справочник характеристик смартфонов

## Педагогическая цель

Показать, как RASA работает с **именованными сущностями**, **слотами** и **формами** (slot filling), а также как подключить **custom action** с обращением к внешней базе данных (CSV через pandas).

## Новые концепты по сравнению с 01_hello_bot

| Концепт | Файл | Что показывает |
|---|---|---|
| Entity | `data/nlu.yml` | Извлечение `phone_model` и `spec_type` из текста |
| Lookup table | `data/nlu.yml` | Список допустимых значений сущности для улучшения распознавания |
| Synonym | `data/nlu.yml` | Нормализация синонимов («аккумулятор» → `battery`) |
| Slot | `domain.yml` | Хранение извлечённых значений между шагами диалога |
| Form (slot filling) | `domain.yml`, `data/rules.yml` | Автоматический переспрос, если обязательный слот не заполнен |
| Custom action | `actions/actions.py` | Python-код, читающий CSV и формирующий ответ |
| EntitySynonymMapper | `config.yml` | Применение синонимов к извлечённым сущностям |

## Сценарии диалога

```
Пользователь: Расскажи про iPhone 15
Бот: iPhone 15 (Apple):
      • Экран: 6.1" Super Retina XDR OLED ...
      • Камера: 48 Мп + 12 Мп ...
      ...

Пользователь: Какая камера?
Бот: Какой телефон вас интересует?
Пользователь: Galaxy S24
Бот: Samsung Galaxy S24 — Камера: 50 Мп + 12 Мп + 10 Мп (телефото 3×)
```

## База данных (phones.csv)

10 моделей, колонки: `model`, `brand`, `screen`, `camera`, `battery`, `ram`, `storage`, `processor`, `price`.

Доступные модели: iPhone 15, iPhone 15 Pro, Samsung Galaxy S24, Samsung Galaxy A55, Google Pixel 8, Xiaomi Redmi Note 13, Xiaomi 14, OnePlus 12, realme 12 Pro+, Honor 200 Pro.

## Команды для запуска

```bash
# 1. Перейти в директорию примера
cd examples/02_phones_bot

# 2. Обучить модель
rasa train

# 3. В отдельном терминале — запустить action server
rasa run actions

# 4. В основном терминале — запустить чат
rasa shell
```

> **Требования:** `conda activate rasa-seminar` в обоих терминалах.

## Как тестировать RASA-проект

Ниже – пошаговый чек-лист, который применим к любому RASA-проекту. Команды выполняются в директории примера (`examples/02_phones_bot/`) при активированном окружении (`conda activate rasa-seminar`).

### Шаг 1 – статическая валидация данных

Проверяет согласованность `domain.yml`, `nlu.yml`, `stories.yml`, `rules.yml`: все ли интенты/entities объявлены, есть ли конфликты между stories и rules.

```bash
rasa data validate
```

Типовые предупреждения, которые можно игнорировать:
- `utterance 'utter_ask_...' is not used in any story or rule` – false positive для utterance'ов, которые вызываются формой по соглашению имён;
- `config file is missing the 'assistant_id' mandatory key` – RASA сама допишет ключ при следующем `rasa train`.

### Шаг 2 – обучение модели

```bash
rasa train
```

Результат – архив в `models/YYYYMMDD-HHMMSS-<name>.tar.gz`. Перед коммитом в репозиторий старые архивы удаляем: держим один текущий или, ещё лучше, добавляем `models/` в `.gitignore`.

### Шаг 3 – запуск action server и REST API

В **двух разных терминалах** (оба – с активным `rasa-seminar`):

```bash
# Терминал 1 – custom actions (порт 5055)
rasa run actions

# Терминал 2 – RASA server с REST API (порт 5005)
rasa run --enable-api --cors "*" -p 5005
```

Сервер готов, когда `GET /status` возвращает JSON с полем `"model_file"`:

```bash
curl http://localhost:5005/status
# {"model_file":"20260421-091355-interior-sound.tar.gz", ...}
```

### Шаг 4 – ручной тест через `rasa shell`

Быстрая проверка «поговорить с ботом» без запуска REST:

```bash
# В третьем терминале (action server должен быть запущен)
rasa shell
```

Полезные режимы:
- `rasa shell nlu` – только NLU: печатает распознанный intent и entities для каждого сообщения, без запуска диалога;
- `rasa interactive` – интерактивное обучение: бот после каждого шага спрашивает «правильно ли я понял?», ошибки сразу попадают в training data.

### Шаг 5 – автоматический тест через REST API

У RASA есть два основных endpoint'а:

| Endpoint | Назначение |
|---|---|
| `POST /model/parse` | Только NLU: intent + entities для текста |
| `POST /webhooks/rest/webhook` | Полный цикл диалога: NLU → Policy → Action → ответ |

**Пример 1 – проверить NLU:**

```bash
curl -X POST http://localhost:5005/model/parse \
     -H "Content-Type: application/json" \
     -d '{"text": "Какая камера у iPhone 15 Pro?"}'
```

Ожидаемый фрагмент ответа:

```json
{
  "intent": {"name": "ask_specific_spec", "confidence": 0.99},
  "entities": [
    {"entity": "spec_type",   "value": "camera",       "extractor": "DIETClassifier"},
    {"entity": "phone_model", "value": "iPhone 15 Pro","extractor": "DIETClassifier"}
  ]
}
```

На что смотреть:
- `intent.name` – совпадает с ожидаемым;
- все нужные entities извлечены, `value` корректен;
- **одна** сущность на одно вхождение (если их две от разных `extractor`'ов – это конфликт в pipeline, см. примечание ниже).

**Пример 2 – полный диалог:**

```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d '{"sender": "test_user_1", "message": "Расскажи про iPhone 15 Pro"}'
```

Ответ – массив сообщений бота:

```json
[{"recipient_id": "test_user_1",
  "text": "iPhone 15 Pro (Apple):\n  • Экран: 6.1\" Super Retina XDR ProMotion ...\n  • Цена, руб.: 119990"}]
```

Поле `sender` – произвольный идентификатор пользователя; один и тот же `sender` в последовательных запросах даёт связный диалог (сохраняется tracker и слоты), разные `sender` – независимые сессии. Сбросить состояние можно командой `/restart`:

```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d '{"sender": "test_user_1", "message": "/restart"}'
```

**Пример 3 – тест формы (slot filling):**

```bash
# Первый запрос без модели – бот должен переспросить
curl -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d '{"sender": "form_test", "message": "Покажи характеристики"}'
# → "Какой телефон вас интересует?"

# Второй запрос от того же sender – слот дозаполняется, action выполняется
curl -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" \
     -d '{"sender": "form_test", "message": "OnePlus 12"}'
# → "OnePlus 12 (OnePlus): • Экран: ..."
```

### Шаг 6 – тесты на основе story-файлов (опционально)

RASA умеет прогонять stories как regression-тесты:

```bash
# Создать tests/test_stories.yml с ожидаемыми диалогами (тот же формат, что stories.yml)
rasa test
```

Отчёты появятся в `results/` (confusion matrix по intent'ам, F1 по entities, статистика по историям).

> ⚠️ **Известная проблема на Windows:** команды `rasa test` и `rasa run` в версии 3.6.x могут падать с `OSError [WinError 123]` при распаковке модели из-за префикса `\\?\` в `local_model_storage.py`. Workaround: в файле `site-packages/rasa/engine/storage/local_model_storage.py` заменить `tar.extractall(f"\\\\?\\{temporary_directory}")` на `tar.extractall(str(temporary_directory))`.

### Чек-лист при отладке «бот отвечает не то, что ожидалось»

1. **NLU работает?** Прогнать `POST /model/parse` – совпадают ли intent и entities с ожиданием?
2. **Несколько entities от разных extractor'ов на одно вхождение?** Это конфликт pipeline (классический случай: `DIETClassifier` даёт `iPhone 15 Pro`, а `RegexEntityExtractor` на том же вхождении – более короткое `iPhone 15` из lookup table). Решение – оставить один extractor или выбирать самое длинное значение в custom action.
3. **Policy выбирает не то действие?** Запустить `rasa interactive` и посмотреть confidence каждой policy на проблемном шаге.
4. **Action падает?** Логи видны в терминале, где запущен `rasa run actions`; для отладки – `logger.debug(...)` внутри action.
5. **Слоты «не запоминаются»?** Проверить `session_config.carry_over_slots_to_new_session` в `domain.yml` и что `mappings` в слоте указан корректно.

## Идеи для самостоятельного задания

1. Добавить в `phones.csv` 3–5 новых моделей и расширить lookup table в `nlu.yml`.
2. Добавить intent `compare_phones` и action, которая сравнивает две модели по одной характеристике.
3. Добавить слот `brand` и intent `ask_by_brand` («Покажи все телефоны Samsung»).
4. Добавить валидацию в форму (`validate_phone_form`): если пользователь ввёл не существующую в базе модель — попросить уточнить.
