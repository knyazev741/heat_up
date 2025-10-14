# Быстрый старт: Добавление и прогрев сессий

## 🚀 Запуск системы (одна команда)

```bash
cd /Users/knyaz/heat_up && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ➕ Добавление сессий

### Один аккаунт (curl)

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

### Много аккаунтов (интерактивный скрипт)

```bash
./bulk_add_sessions.sh
```

**Что происходит при добавлении:**
1. ✅ Генерируется уникальная персона (LLM)
2. ✅ Находятся 20 релевантных каналов (SearchAgent)
3. ✅ Аккаунт готов к прогреву

---

## ▶️ Запуск прогрева

### Автоматический (рекомендуется)

```bash
# Запустить scheduler - будет прогревать все аккаунты N раз в день
curl -X POST http://localhost:8000/scheduler/start

# Проверить что работает
curl http://localhost:8000/scheduler/status
```

### Ручной (тестовый прогрев)

```bash
# Прогреть аккаунт #1 прямо сейчас
curl -X POST http://localhost:8000/accounts/1/warmup-now \
  -H "Content-Type: application/json" \
  -d '{"action_count": 5}'
```

---

## 📊 Проверка статуса

### Быстрая проверка

```bash
./check_accounts.sh
```

Покажет:
- Список всех аккаунтов (ID, телефон, stage, активность)
- Общую статистику
- Статус scheduler
- Ближайшие запуски

### Детали конкретного аккаунта

```bash
curl http://localhost:8000/accounts/1
```

Покажет:
- Персону (имя, возраст, профессия, интересы)
- Найденные каналы (с оценками релевантности)
- Историю прогрева

### Здоровье аккаунта

```bash
curl http://localhost:8000/accounts/1/health
```

Покажет:
- Health score (0-1)
- Проблемы (если есть)
- Рекомендации

---

## 📝 Логи

### В реальном времени

```bash
tail -f logs/heat_up.log
```

### Фильтр по номеру

```bash
grep "+79991234567" logs/heat_up.log
```

### Только ошибки

```bash
grep "ERROR" logs/heat_up.log
```

---

## 🔧 Управление

### Изменить частоту прогрева

```bash
curl -X PUT http://localhost:8000/accounts/1/update \
  -H "Content-Type: application/json" \
  -d '{"daily_activity_count": 6}'
```

### Регенерировать персону

```bash
curl -X POST http://localhost:8000/accounts/1/generate-persona
```

### Обновить список каналов

```bash
curl -X POST http://localhost:8000/accounts/1/refresh-chats
```

### Деактивировать аккаунт

```bash
curl -X DELETE http://localhost:8000/accounts/1/delete
```

### Остановить scheduler

```bash
curl -X POST http://localhost:8000/scheduler/stop
```

---

## 📈 Мониторинг

### Общая статистика

```bash
curl http://localhost:8000/statistics
```

### Дневной отчет

```bash
curl http://localhost:8000/statistics/daily
```

### Удобный мониторинг

```bash
./monitor.sh
```

---

## 🗂️ База данных

### Посмотреть аккаунты

```bash
sqlite3 sessions.db "SELECT account_id, phone_number, stage, is_active FROM accounts;"
```

### Посмотреть персоны

```bash
sqlite3 sessions.db "SELECT account_id, generated_name, occupation, city FROM personas;"
```

### Посмотреть историю

```bash
sqlite3 sessions.db "SELECT * FROM warmup_sessions ORDER BY created_at DESC LIMIT 10;"
```

---

## ⚡ Типичный workflow

```bash
# 1. Запустить сервер
uvicorn main:app --port 8000 --reload

# 2. Добавить сессии (в другом терминале)
./bulk_add_sessions.sh

# 3. Проверить что добавились
./check_accounts.sh

# 4. Запустить автоматический прогрев
curl -X POST http://localhost:8000/scheduler/start

# 5. Мониторить
./monitor.sh

# 6. Смотреть логи
tail -f logs/heat_up.log
```

---

## 🎯 Рекомендации

1. **daily_activity_count**: 3-5 раз в день оптимально
2. **Не меняй персону** во время прогрева (14 дней)
3. **Мониторь первые 2-3 дня** - убедись что нет ошибок
4. **Используй scheduler** - ручной прогрев только для тестов
5. **Проверяй health** раз в день первую неделю

---

## 🆘 Troubleshooting

### Сервер не запускается

```bash
# Проверить что порт свободен
lsof -i :8000

# Если занят - убить процесс
kill -9 <PID>
```

### Scheduler не работает

```bash
# Проверить статус
curl http://localhost:8000/scheduler/status

# Если stopped - запустить
curl -X POST http://localhost:8000/scheduler/start
```

### Ошибки в логах

```bash
# Посмотреть последние ошибки
grep "ERROR" logs/heat_up.log | tail -20

# Распространенные ошибки:
# - "Session not found" → проверь session_id
# - "OpenAI API error" → проверь OPENAI_API_KEY в .env
# - "Telegram API error" → проверь что Telegram API работает
```

### LLM не генерирует персону

```bash
# Проверь API key
grep OPENAI_API_KEY .env

# Проверь баланс OpenAI
# https://platform.openai.com/usage
```

---

## 📚 Полная документация

- `HOWTO_ADD_SESSIONS.md` - подробная инструкция
- `WARMUP_SYSTEM_GUIDE.md` - архитектура системы
- `SEARCH_AGENT_README.md` - как работает поиск каналов
- `API_EXAMPLES.sh` - примеры всех API вызовов

---

**Все готово! Добавляй сессии и запускай прогрев! 🔥**

