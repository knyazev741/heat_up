# Как добавить сессии в систему прогрева

## Шаг 1: Запуск системы

```bash
cd /Users/knyaz/heat_up
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Система запустится на `http://localhost:8000`

---

## Шаг 2: Добавление сессии

### Вариант А: Через API (curl)

```bash
curl -X POST http://localhost:8000/accounts/add \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your_session_id_here",
    "phone_number": "+79991234567",
    "country": "Russia",
    "daily_activity_count": 4
  }'
```

**Параметры:**
- `session_id` - ID сессии из твоей основной системы
- `phone_number` - номер телефона аккаунта
- `country` - страна (Russia, USA, Kazakhstan и т.д.)
- `daily_activity_count` - сколько раз в день прогревать (3-5 рекомендуется)

**Что произойдет:**
1. ✅ Сессия добавится в БД
2. ✅ LLM сгенерирует уникальную персону
3. ✅ SearchAgent найдет 20 релевантных каналов
4. ✅ Аккаунт готов к прогреву!

### Вариант Б: Через Python скрипт

Создай `add_session.py`:

```python
import httpx
import asyncio

async def add_session(session_id, phone, country="Russia", daily_count=4):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/accounts/add",
            json={
                "session_id": session_id,
                "phone_number": phone,
                "country": country,
                "daily_activity_count": daily_count
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Аккаунт добавлен: {data['phone_number']}")
            print(f"   Account ID: {data['account_id']}")
            print(f"   Персона: {data.get('persona_generated', False)}")
            print(f"   Каналы: {data.get('chats_discovered', 0)}")
        else:
            print(f"❌ Ошибка: {response.text}")

# Использование
asyncio.run(add_session(
    session_id="session_123",
    phone="+79991234567",
    country="Russia",
    daily_count=4
))
```

### Вариант В: Интерактивный скрипт (массовое добавление)

Используй готовый скрипт:

```bash
./add_accounts_interactive.sh
```

Введи данные по одной сессии за раз.

---

## Шаг 3: Проверка добавленных аккаунтов

### Посмотреть все аккаунты

```bash
curl http://localhost:8000/accounts
```

**Ответ:**
```json
[
  {
    "account_id": 1,
    "phone_number": "+79991234567",
    "country": "Russia",
    "stage": 1,
    "is_active": true,
    "last_warmup_date": null,
    "daily_activity_count": 4
  }
]
```

### Детали конкретного аккаунта

```bash
curl http://localhost:8000/accounts/1
```

**Ответ:**
```json
{
  "account_id": 1,
  "phone_number": "+79991234567",
  "stage": 1,
  "persona": {
    "generated_name": "Алексей Иванов",
    "age": 32,
    "occupation": "программист",
    "city": "Москва",
    "interests": ["технологии", "путешествия", "музыка"]
  },
  "discovered_chats": [
    {
      "chat_username": "@moscow_city",
      "relevance_score": 0.95,
      "relevance_reason": "Локальный чат города Москва"
    }
  ],
  "recent_sessions": []
}
```

---

## Шаг 4: Запуск прогрева

### Автоматический прогрев (рекомендуется)

Scheduler автоматически прогревает аккаунты N раз в день.

**Запустить scheduler:**

```bash
curl -X POST http://localhost:8000/scheduler/start
```

**Проверить статус:**

```bash
curl http://localhost:8000/scheduler/status
```

**Ответ:**
```json
{
  "running": true,
  "accounts_tracked": 5,
  "next_runs": [
    {
      "account_id": 1,
      "phone_number": "+79991234567",
      "next_run_time": "2025-10-14T15:30:00"
    }
  ]
}
```

### Ручной прогрев (разовый)

Если хочешь прогреть конкретный аккаунт прямо сейчас:

```bash
curl -X POST http://localhost:8000/accounts/1/warmup-now \
  -H "Content-Type: application/json" \
  -d '{
    "action_count": 5
  }'
```

**Что произойдет:**
1. ✅ LLM сгенерирует 5 действий на основе персоны
2. ✅ Действия будут выполнены через Telegram API
3. ✅ Все запишется в историю

---

## Шаг 5: Мониторинг

### Общая статистика

```bash
curl http://localhost:8000/statistics
```

**Ответ:**
```json
{
  "total_accounts": 5,
  "active_accounts": 5,
  "total_warmup_sessions": 23,
  "total_actions_performed": 115,
  "accounts_by_stage": {
    "1": 2,
    "2": 2,
    "3": 1
  }
}
```

### Дневной отчет

```bash
curl http://localhost:8000/statistics/daily
```

### Здоровье аккаунта

```bash
curl http://localhost:8000/accounts/1/health
```

**Ответ:**
```json
{
  "account_id": 1,
  "health_score": 0.85,
  "issues": [],
  "recommendations": [
    "Account is warming up well. Continue current pattern."
  ],
  "last_activity": "2025-10-14T14:20:00"
}
```

---

## Шаг 6: Логи

### Смотреть в реальном времени

```bash
tail -f logs/heat_up.log
```

### Фильтровать по аккаунту

```bash
grep "+79991234567" logs/heat_up.log
```

### Использовать monitor.sh

```bash
./monitor.sh
```

Покажет:
- Статус scheduler
- Общую статистику
- Дневной отчет

---

## Полный рабочий процесс

```bash
# 1. Запустить сервер
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 2. Добавить сессию (в другом терминале)
curl -X POST http://localhost:8000/accounts/add \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_001",
    "phone_number": "+79991234567",
    "country": "Russia",
    "daily_activity_count": 4
  }'

# 3. Проверить что добавилось
curl http://localhost:8000/accounts

# 4. Запустить автоматический прогрев
curl -X POST http://localhost:8000/scheduler/start

# 5. Мониторить
./monitor.sh

# 6. Смотреть логи
tail -f logs/heat_up.log
```

---

## Массовое добавление сессий

Создай `bulk_add.sh`:

```bash
#!/bin/bash

# Список сессий (замени на свои)
sessions=(
  "session_001:+79991234567:Russia"
  "session_002:+79992345678:Russia"
  "session_003:+79993456789:Kazakhstan"
)

for session_data in "${sessions[@]}"; do
  IFS=':' read -r session_id phone country <<< "$session_data"
  
  echo "Добавляю: $phone ($session_id)"
  
  curl -X POST http://localhost:8000/accounts/add \
    -H "Content-Type: application/json" \
    -d "{
      \"session_id\": \"$session_id\",
      \"phone_number\": \"$phone\",
      \"country\": \"$country\",
      \"daily_activity_count\": 4
    }"
  
  echo ""
  sleep 2  # Пауза между добавлениями
done

echo "✅ Все сессии добавлены!"
```

Запуск:

```bash
chmod +x bulk_add.sh
./bulk_add.sh
```

---

## FAQ

### Что такое session_id?

Это ID сессии из твоей основной системы (из API `/api/external/sessions`). Heat_up использует его для отправки команд через Telegram API.

### Сколько сессий можно добавить?

Неограниченно. Scheduler управляет прогревом всех аккаунтов автоматически.

### Как изменить частоту прогрева?

```bash
curl -X PUT http://localhost:8000/accounts/1/update \
  -H "Content-Type: application/json" \
  -d '{"daily_activity_count": 6}'
```

### Как удалить сессию?

```bash
curl -X DELETE http://localhost:8000/accounts/1/delete
```

Аккаунт деактивируется (is_active=false), но данные сохранятся в БД.

### Где хранятся данные?

SQLite база: `sessions.db`

Посмотреть:
```bash
sqlite3 sessions.db "SELECT * FROM accounts;"
```

---

## Рекомендации

1. **Начни с 2-3 сессий** - протестируй систему
2. **Запусти scheduler** - автоматизация критична
3. **Мониторь логи первые 2-3 дня** - убедись что все работает
4. **Используй daily_activity_count = 3-5** - оптимальная частота
5. **Не меняй персоны и каналы** во время прогрева (14 дней)

---

**Готово! Теперь можешь добавлять сессии и запускать прогрев! 🚀**

