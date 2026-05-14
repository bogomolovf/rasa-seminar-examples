# Установка окружения для RASA — вариант без Anaconda

Этот гайд для тех, у кого установлен **чистый Python** (без Anaconda/Miniconda).

RASA 3.6.x поддерживает только Python **3.8–3.10**. Если у вас Python 3.11 или новее — сначала установите Python 3.10 (старую версию Python можно держать параллельно, они не конфликтуют).

---

## Шаг 0. Проверить версию Python

```bash
python --version
```

- Если `3.8.x`–`3.10.x` — переходите сразу к Шагу 2.
- Если `3.11.x`, `3.12.x` или новее — сначала выполните Шаг 1.

---

## Шаг 1. Установить Python 3.10 (если нужно)

### Windows

1. Скачайте установщик с официального сайта: [python.org/downloads](https://www.python.org/downloads/release/python-31011/)  
   Выбирайте **Windows installer (64-bit)**.

2. При установке **обязательно** поставьте галочку **«Add python.exe to PATH»** — но только если у вас ещё нет Python в PATH. Если уже есть другая версия, галочку **не ставьте** — воспользуйтесь py-launcher (см. ниже).

3. Проверьте установку через py-launcher (он появляется автоматически вместе с Python на Windows):

```bash
py -0
```

В списке должна быть строка `-3.10-64`.

### macOS

```bash
brew install python@3.10
```

После установки Python 3.10 доступен как `python3.10`.

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev
```

---

## Шаг 2. Создать виртуальное окружение

Перейдите в **корневую папку репозитория** (там, где лежит этот файл) и создайте окружение `.venv`:

### Windows (py-launcher — рекомендуется)

```bash
py -3.10 -m venv .venv
```

### Windows (если python 3.10 уже в PATH как `python`)

```bash
python -m venv .venv
```

### macOS / Linux

```bash
python3.10 -m venv .venv
```

После выполнения появится папка `.venv` — это и есть изолированное окружение.

---

## Шаг 3. Активировать окружение

### Windows (Command Prompt / PowerShell)

```bash
.venv\Scripts\activate
```

### macOS / Linux

```bash
source .venv/bin/activate
```

Командная строка должна измениться: `(.venv) C:\...` или `(.venv) user@host:...`

Убедитесь, что используется правильный Python:

```bash
python --version
# Python 3.10.x

where python      # Windows
# C:\...\rasa-seminar-examples\.venv\Scripts\python.exe

which python      # macOS / Linux
# /path/to/rasa-seminar-examples/.venv/bin/python
```

---

## Шаг 4. Обновить pip

Перед установкой тяжёлых пакетов обновите pip — старые версии могут некорректно обрабатывать зависимости:

```bash
python -m pip install --upgrade pip
```

---

## Шаг 5. Установить RASA

```bash
pip install "rasa==3.6.*"
```

> **Внимание:** RASA тянет тяжёлые зависимости (TensorFlow ~300 МБ, scikit-learn и др.).
> Установка займёт **5–15 минут** в зависимости от скорости интернета.
> Если pip падает с сетевой ошибкой на середине — просто запустите команду повторно,
> все уже скачанные пакеты закешированы.

### Возможная проблема на Windows: ошибка сборки C-расширений

Некоторые пакеты RASA компилируются из исходников. Если видите ошибку вида `error: Microsoft Visual C++ 14.0 or greater is required`, установите **Microsoft C++ Build Tools**:

1. Скачайте: [visualstudio.microsoft.com/visual-cpp-build-tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. При установке выберите компонент **«Разработка классических приложений на C++»**.
3. После установки перезапустите терминал и повторите `pip install "rasa==3.6.*"`.

---

## Шаг 6. Проверить установку

```bash
rasa --version
```

Ожидаемый вывод:

```
Rasa Version      :         3.6.21
Minimum Compatible Version: 3.6.21
Rasa SDK Version  :         3.6.2
Python Version    :         3.10.x
Operating System  :         ...
Python Path       :         .../​.venv/Scripts/python.exe
```

Путь к Python должен указывать внутрь папки `.venv`.

---

## Шаг 7. Запуск примера

**Важно:** активировать окружение нужно каждый раз при открытии нового терминала.

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### Примеры без custom actions (например, 01_hello_bot)

Нужен **один** терминал:

```bash
cd examples/01_hello_bot
rasa train
rasa shell
```

### Примеры с custom actions (например, 02_phones_bot)

Нужны **два** терминала, оба с активированным окружением:

**Терминал 1** — action server:
```bash
source .venv/bin/activate   # или .venv\Scripts\activate на Windows
cd examples/02_phones_bot
rasa run actions
```

**Терминал 2** — чат:
```bash
source .venv/bin/activate
cd examples/02_phones_bot
rasa train
rasa shell
```

> Сначала запустите action server (Терминал 1), затем `rasa shell` (Терминал 2).

---

## Деактивация окружения

```bash
deactivate
```

---

## Частые проблемы

| Симптом | Причина | Решение |
|---|---|---|
| `rasa: command not found` | окружение не активировано | выполните `source .venv/bin/activate` или `.venv\Scripts\activate` |
| `pip install` застревает на загрузке | медленная сеть или DNS-сбой | повторите команду — pip докачает с места обрыва |
| `error: Microsoft Visual C++ 14.0 required` | нет компилятора C++ | установите Build Tools (см. Шаг 5) |
| `python --version` показывает 3.12 внутри venv | venv создан не от Python 3.10 | удалите `.venv` и пересоздайте с `py -3.10 -m venv .venv` |
| `ModuleNotFoundError: No module named 'rasa'` | Python не из venv | проверьте `which python` / `where python` и активируйте окружение |
| SQLAlchemy warning при `rasa --version` | косметический баг rasa 3.6.x | игнорируйте, на работу бота не влияет |
