# Способы добавления сессий - Сравнение

## 1️⃣ Интерактивный скрипт (для ручного ввода)

**Скрипт:** `./bulk_add_sessions.sh`

**Когда использовать:**
- У тебя 2-10 сессий
- Хочешь вводить данные вручную
- Нужен контроль на каждом шаге

**Как работает:**
```bash
./bulk_add_sessions.sh

# Спросит:
Сколько сессий хочешь добавить? 3

# Для каждой сессии:
Session ID: session_001
Номер телефона: +79991234567
Страна (по умолчанию Russia): Russia
Частота прогрева (по умолчанию 4): 4
```

**Плюсы:**
- ✅ Удобно для небольшого количества
- ✅ Видишь результат сразу
- ✅ Можно пропустить (Enter = дефолт)

**Минусы:**
- ❌ Неудобно для >10 сессий
- ❌ Нужно вводить вручную

---

## 2️⃣ Из файла (автоматический)

**Скрипт:** `./add_from_file.sh sessions.txt`

**Когда использовать:**
- У тебя много сессий (10+)
- Данные уже есть в списке/таблице
- Нужна автоматизация

**Подготовка:**

1. Создай файл `sessions.txt`:
```bash
session_001|+79991234567|Russia|4
session_002|+79992345678|Russia|5
session_003|+77771234567|Kazakhstan|3
```

2. Запусти:
```bash
./add_from_file.sh sessions.txt
```

**Формат файла:**
```
session_id|phone_number|country|daily_count
```

**Плюсы:**
- ✅ Быстро для большого количества
- ✅ Можно подготовить заранее
- ✅ Легко импортировать из Excel/CSV

**Минусы:**
- ❌ Нужно подготовить файл

**Как создать из Excel/CSV:**
```bash
# В Excel/Google Sheets:
# Колонка A: session_id
# Колонка B: phone_number
# Колонка C: country
# Колонка D: daily_count

# Экспорт как CSV, затем:
cat sessions.csv | sed 's/,/|/g' > sessions.txt
```

---

## 3️⃣ Одна команда (curl)

**Команда:**
```bash
curl -X POST http://localhost:8000/accounts/add \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_001",
    "phone_number": "+79991234567",
    "country": "Russia",
    "daily_activity_count": 4
  }'
```

**Когда использовать:**
- Добавляешь 1 сессию
- Нужен быстрый тест
- Интеграция из другого скрипта

**Плюсы:**
- ✅ Максимально быстро для 1 сессии
- ✅ Можно из любого скрипта
- ✅ Прямой API вызов

**Минусы:**
- ❌ Неудобно для нескольких сессий

---

## 4️⃣ Python скрипт (программная интеграция)

**Скрипт:** создай свой

```python
import httpx
import asyncio

async def add_sessions_bulk(sessions_list):
    async with httpx.AsyncClient() as client:
        for session in sessions_list:
            response = await client.post(
                "http://localhost:8000/accounts/add",
                json=session
            )
            print(f"Added: {session['phone_number']}")

sessions = [
    {
        "session_id": "session_001",
        "phone_number": "+79991234567",
        "country": "Russia",
        "daily_activity_count": 4
    },
    # ... еще сессии
]

asyncio.run(add_sessions_bulk(sessions))
```

**Когда использовать:**
- Интеграция с другой системой
- Нужна сложная логика
- Данные из базы данных

**Плюсы:**
- ✅ Полный контроль
- ✅ Можно добавить валидацию
- ✅ Интеграция с любым источником

**Минусы:**
- ❌ Нужно писать код

---

## 🎯 Рекомендации

### У тебя 1-5 сессий?
→ **`./bulk_add_sessions.sh`** (интерактивный)

### У тебя 10-100 сессий?
→ **`./add_from_file.sh sessions.txt`** (из файла)

### Данные в Excel/Google Sheets?
→ Экспорт в CSV → конвертация в `sessions.txt` → **`./add_from_file.sh`**

### Нужна интеграция с другой системой?
→ **Python скрипт** или прямые **curl** вызовы

---

## 📝 Примеры файлов

### sessions.txt (простой)
```
session_001|+79991234567|Russia|4
session_002|+79992345678|Russia|5
```

### sessions.txt (с комментариями)
```
# Московские аккаунты
session_001|+79991234567|Russia|4
session_002|+79992345678|Russia|4

# Казахстан
session_003|+77771234567|Kazakhstan|3

# Дефолтные значения (Russia, 4)
session_004|+79993456789
```

### Конвертация из CSV
```bash
# Если у тебя sessions.csv:
# session_001,+79991234567,Russia,4
# session_002,+79992345678,Russia,5

cat sessions.csv | sed 's/,/|/g' > sessions.txt
./add_from_file.sh sessions.txt
```

---

## ⚡ Quick Start

**Самый простой способ:**

```bash
# 1. Скопируй пример
cp sessions.txt.example sessions.txt

# 2. Отредактируй (замени на свои данные)
nano sessions.txt

# 3. Добавь все сразу
./add_from_file.sh sessions.txt
```

---

## 🔍 Проверка результата

После добавления любым способом:

```bash
# Проверить что добавилось
./check_accounts.sh

# Или через API
curl http://localhost:8000/accounts

# Детали конкретного аккаунта
curl http://localhost:8000/accounts/1
```

---

**Выбирай удобный способ и добавляй сессии! 🚀**

