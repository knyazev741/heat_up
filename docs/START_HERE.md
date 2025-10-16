# 🚀 Быстрый старт с логированием

## 1️⃣ Запуск сервиса

```bash
cd /Users/knyaz/heat_up

# Вариант A: В консоли (видишь логи сразу)
./venv/bin/python main.py

# Вариант B: В фоне
./venv/bin/python main.py &
```

## 2️⃣ Тестирование

```bash
# Запусти warmup
curl -X POST http://localhost:8080/warmup/my_test_session

# Проверь здоровье
curl http://localhost:8080/health

# Посмотри историю сессии
curl http://localhost:8080/sessions/my_test_session/history | python -m json.tool
```

## 3️⃣ Просмотр логов (для отладки)

### Быстрые команды

```bash
# Последние 50 строк
./view_logs.sh

# Следить в реальном времени (live tail)
./view_logs.sh live

# Что отправляется в LLM и что он отвечает
./view_logs.sh llm

# Какие действия выполняются
./view_logs.sh actions

# Только ошибки
./view_logs.sh errors

# Справка
./view_logs.sh help
```

### Где логи?

- **Файл**: `logs/heat_up.log` - ВСЁ логируется сюда
- **Консоль**: stdout - если запускал без `&`

## 4️⃣ Что логируется?

### 🤖 LLM взаимодействие

```
====================================================================================================
📤 SENDING TO LLM (GPT-4o-mini)
====================================================================================================
SYSTEM PROMPT:
You are simulating natural behavior for a new Telegram user...

Available channels to interact with:
- @durov: Pavel Durov's official channel
- @telegram: Telegram official news
- @rt_russian: RT на русском
... (все каналы из channels_data.json и bots_data.json)

Available action types (use variety!):
1. join_channel
2. read_messages
3. idle
4. react_to_message  ← новое!
5. message_bot       ← новое!
6. view_profile      ← новое!
...
----------------------------------------------------------------------------------------------------
USER PROMPT:
Generate a natural action sequence for this Telegram user...
====================================================================================================
📥 RECEIVED FROM LLM
====================================================================================================
RAW RESPONSE:
[
  {"action": "view_profile", "channel_username": "@telegram", ...},
  {"action": "join_channel", "channel_username": "@telegram", ...},
  {"action": "react_to_message", "emoji": "🔥", ...}
]
====================================================================================================
✅ VALIDATION COMPLETE: 12 / 12 actions passed
  1. [view_profile] Checking out the official channel
  2. [join_channel] Looks interesting, joining
  3. [react_to_message] Loved this post!
  ...
```

### 🎬 Выполнение действий

```
====================================================================================================
🎬 EXECUTING ACTION #1/12: VIEW_PROFILE
====================================================================================================
Full action: {
  "action": "view_profile",
  "channel_username": "@telegram",
  "duration_seconds": 5,
  "reason": "Checking out the official channel"
}
----------------------------------------------------------------------------------------------------
✅ ACTION SUCCEEDED: view_profile
Result: {
  "action": "view_profile",
  "channel": "@telegram",
  "duration": 5,
  "status": "completed"
}
====================================================================================================
```

## 5️⃣ Типичные сценарии отладки

### "LLM генерирует странные действия"

```bash
# Смотри что ты ему отправляешь
./view_logs.sh llm | grep -A 200 "SYSTEM PROMPT"

# Смотри что он отвечает
./view_logs.sh llm | grep -A 50 "RAW RESPONSE"
```

### "Действия не выполняются"

```bash
# Смотри детали выполнения
./view_logs.sh actions

# Или все ошибки
./view_logs.sh errors
```

### "Хочу следить в реальном времени"

Открой **2 терминала**:

**Терминал 1:**
```bash
./venv/bin/python main.py
```

**Терминал 2:**
```bash
# Запускай warmup и смотри логи
curl -X POST http://localhost:8080/warmup/test_123

# Или в другом терминале
./view_logs.sh live
```

## 6️⃣ Что изменилось? (новое в системе)

### ✅ Расширенные действия (было 3 → стало 6)

- `react_to_message` - ставить реакции 👍❤️🔥😂😮🎉👏
- `message_bot` - писать ботам (@telegraph, @gif, @wiki, etc.)
- `view_profile` - смотреть профили каналов

### ✅ Список реальных каналов и ботов

- **Каналы**: `channels_data.json` (30+ каналов)
- **Боты**: `bots_data.json` (15 ботов)

### ✅ Динамические промпты

- **Новый пользователь**: "You are simulating a new Telegram user..."
- **Returning пользователь**: "You're back! Last active: 2 hours ago..."

### ✅ Полное логирование

Каждый шаг логируется с деталями для отладки!

## 7️⃣ Остановка сервиса

```bash
# Найти процесс
ps aux | grep "python main.py"

# Убить
pkill -f "python main.py"

# Или жестко
pkill -9 -f "python main.py"
```

## 📚 Дополнительная документация

- `LOGGING_GUIDE.md` - Детальное руководство по логированию
- `QUICK_DEBUG.md` - Шпаргалка по отладке
- `TGSTAT_INTEGRATION.md` - TGStat API и история сессий
- `README.md` - Общее описание проекта

---

**Готов к отладке?** Запускай сервис и смотри логи! 🎯

