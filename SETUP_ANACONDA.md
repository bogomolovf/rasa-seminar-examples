# Установка окружения для RASA — вариант с Anaconda

Этот гайд для тех, у кого установлена **Anaconda** (или Miniconda), но версия Python в базовом окружении **новее 3.10** (например, 3.11, 3.12).

RASA 3.6.x поддерживает только Python **3.8–3.10**. Conda позволяет создать отдельное окружение с нужной версией, не трогая базовую установку.

---

## Шаг 0. Проверить, что Anaconda установлена

Откройте **Anaconda Prompt** (или обычный терминал, если conda добавлена в PATH) и выполните:

```bash
conda --version
```

Ожидаемый вывод: `conda 24.x.x` или похожий. Если команда не найдена — установите [Miniconda](https://docs.conda.io/en/latest/miniconda.html).

Проверьте текущую версию Python:

```bash
python --version
```

Если вывод `Python 3.11.x` или новее — вам нужен отдельный env с 3.10. Продолжайте по этому гайду.

---

## Шаг 1. Создать conda-окружение с Python 3.10

```bash
conda create -n rasa-seminar python=3.10 -y
```

Conda скачает и установит Python 3.10 в изолированную папку (обычно `~/.conda/envs/rasa-seminar`). Это занимает 1–2 минуты.

Проверьте, что окружение создалось:

```bash
conda env list
```

В списке должна появиться строка `rasa-seminar`.

---

## Шаг 2. Исправить потенциальную проблему с user-site (только Windows)

> **Почему это важно.** На Windows pip может устанавливать пакеты не в conda-окружение,
> а в общую пользовательскую папку `%APPDATA%\Python\Python310\site-packages`,
> которая видна всем интерпретаторам Python 3.10 на машине.
> В итоге окружение не изолировано, а бинарник `rasa.exe` не попадает в env.

Закрепите переменную окружения `PYTHONNOUSERSITE=1` внутри нашего env:

```bash
conda env config vars set -n rasa-seminar PYTHONNOUSERSITE=1
```

Это разовая настройка — она сохранится навсегда для данного окружения.

---

## Шаг 3. Активировать окружение

```bash
conda activate rasa-seminar
```

Командная строка должна измениться: `(rasa-seminar) C:\...`

Убедитесь, что используется правильный Python:

```bash
python --version
# Python 3.10.x
where python
# C:\Users\<user>\.conda\envs\rasa-seminar\python.exe
```

---

## Шаг 4. Установить RASA

```bash
pip install "rasa==3.6.*"
```

> **Внимание:** RASA тянет тяжёлые зависимости (TensorFlow ~300 МБ, scikit-learn и др.).
> Установка займёт **5–15 минут** в зависимости от скорости интернета.
> Если pip падает с сетевой ошибкой на середине — просто запустите команду повторно,
> все уже скачанные пакеты закешированы.

---

## Шаг 5. Проверить установку

```bash
rasa --version
```

Ожидаемый вывод:

```
Rasa Version      :         3.6.21
Minimum Compatible Version: 3.6.21
Rasa SDK Version  :         3.6.2
Python Version    :         3.10.x
Operating System  :         Windows-...
Python Path       :         C:\Users\<user>\.conda\envs\rasa-seminar\python.exe
```

Если `rasa` не найден — убедитесь, что окружение активировано (`conda activate rasa-seminar`) и путь в выводе `Python Path` указывает на conda env, а не на `AppData\Roaming`.

---

## Шаг 6. Запуск примера

Каждый раз перед работой активируйте окружение:

```bash
conda activate rasa-seminar
```

### Примеры без custom actions (например, 01_hello_bot)

Нужен **один** терминал:

```bash
conda activate rasa-seminar
cd examples/01_hello_bot
rasa train
rasa shell
```

### Примеры с custom actions (например, 02_phones_bot)

Нужны **два** терминала, оба с активированным окружением:

**Терминал 1** — action server:
```bash
conda activate rasa-seminar
cd examples/02_phones_bot
rasa run actions
```

**Терминал 2** — чат:
```bash
conda activate rasa-seminar
cd examples/02_phones_bot
rasa train
rasa shell
```

> Сначала запустите action server (Терминал 1), затем `rasa shell` (Терминал 2).

---

## Деактивация окружения

Когда закончили работу:

```bash
conda deactivate
```

---

## Частые проблемы

| Симптом | Причина | Решение |
|---|---|---|
| `rasa: command not found` после установки | окружение не активировано или PYTHONNOUSERSITE не применён | выполните Шаг 2 и переактивируйте env |
| `pip install` застревает на загрузке | медленная сеть или DNS-сбой | повторите команду — pip докачает с места обрыва |
| `ModuleNotFoundError: No module named 'rasa'` | Python не из conda env | проверьте `where python`, активируйте окружение |
| SQLAlchemy warning при запуске `rasa --version` | известный косметический баг rasa 3.6.x | игнорируйте, на работу бота не влияет |
| `conda activate` не работает в PowerShell | PowerShell не инициализирован для conda | используйте **Anaconda Prompt** или выполните `conda init powershell` |
