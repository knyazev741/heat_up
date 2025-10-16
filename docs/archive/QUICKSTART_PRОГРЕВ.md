# Быстрый старт - Прогрев аккаунтов

## 1. Запуск сервиса

```bash
# Из директории heat_up
cd /Users/knyaz/heat_up

# Активировать venv (если еще не активирован)
source venv/bin/activate

# Запустить сервис
python main.py
```

Сервис запустится на `http://localhost:8080`

**Важно:** Scheduler запускается автоматически при старте (если `SCHEDULER_ENABLED=true` в `.env`)

## 2. Добавление аккаунтов для прогрева

### Вариант 1: Через curl

```bash
# Добавить первый аккаунт
curl -X POST http://localhost:8080/accounts/add \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "твой_session_uid_1",
    "phone_number": "+79991234567",
    "country": "Russia",
    "daily_activity_count": 3
  }'

# Добавить второй аккаунт  
curl -X POST http://localhost:8080/accounts/add \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "твой_session_uid_2",
    "phone_number": "+79991234568",
    "country": "Russia",
    "daily_activity_count": 4
  }'

# Добавить третий аккаунт
curl -X POST http://localhost:8080/accounts/add \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "твой_session_uid_3",
    "phone_number": "+79991234569",
    "country": "Russia",
    "daily_activity_count": 3
  }'
```

**Параметры:**
- `session_id` - UID сессии из твоей основной системы
- `phone_number` - номер телефона аккаунта
- `country` - страна (опционально, определится автоматически)
- `daily_activity_count` - сколько раз в день прогревать (2-5, рекомендую 3)

### Вариант 2: Через Python скрипт

Создай файл `add_accounts.py`:

```python
import httpx
import json

accounts = [
    {"session_id": "session_1", "phone_number": "+79991234567"},
    {"session_id": "session_2", "phone_number": "+79991234568"},
    {"session_id": "session_3", "phone_number": "+79991234569"},
]

for acc in accounts:
    response = httpx.post(
        "http://localhost:8080/accounts/add",
        json={
            "session_id": acc["session_id"],
            "phone_number": acc["phone_number"],
            "daily_activity_count": 3
        }
    )
    print(f"Added {acc['session_id']}: {response.json()}")
```

Запусти: `python add_accounts.py`

## 3. Проверка статуса

### Посмотреть все аккаунты

```bash
curl http://localhost:8080/accounts | jq
```

Вернет список всех аккаунтов с их статусами.

### Детали конкретного аккаунта

```bash
# Получить ID из предыдущего запроса
ACCOUNT_ID=1

curl http://localhost:8080/accounts/$ACCOUNT_ID | jq
```

Покажет:
- Личность (имя, возраст, интересы)
- Найденные чаты
- Последние 10 сессий прогрева
- Статистику

### Проверить здоровье аккаунта

```bash
curl http://localhost:8080/accounts/$ACCOUNT_ID/health | jq
```

Вернет:
- Health score (0-100)
- Выявленные проблемы
- Рекомендации

### Статус scheduler

```bash
curl http://localhost:8080/scheduler/status | jq
```

Покажет:
- Запущен ли scheduler
- Сколько аккаунтов в работе
- Когда следующая проверка

### Общая статистика

```bash
curl http://localhost:8080/statistics | jq
```

### Ежедневный отчет

```bash
curl http://localhost:8080/statistics/daily | jq
```

## 4. Просмотр логов

### В реальном времени

```bash
# Основной лог
tail -f logs/heat_up.log

# С цветовой подсветкой (если есть ccze)
tail -f logs/heat_up.log | ccze -A

# Только ошибки
tail -f logs/heat_up.log | grep -i error

# Только warmup события
tail -f logs/heat_up.log | grep -i warmup
```

### Поиск по логам

```bash
# Найти все прогревы для session_id
grep "session_abc123" logs/heat_up.log

# Найти все ошибки за сегодня
grep "$(date +%Y-%m-%d)" logs/heat_up.log | grep ERROR

# Последние 100 строк
tail -100 logs/heat_up.log

# Найти FloodWait ошибки
grep -i "flood" logs/heat_up.log
```

## 5. Ручной запуск прогрева

Если хочешь запустить прогрев немедленно (вне расписания):

```bash
ACCOUNT_ID=1
curl -X POST http://localhost:8080/accounts/$ACCOUNT_ID/warmup-now | jq
```

Система:
1. Создаст личность (если еще нет)
2. Найдет релевантные чаты (если нужно)
3. Сгенерирует план действий для текущей стадии
4. Выполнит действия
5. Сохранит результаты

## 6. Управление scheduler

### Остановить (если нужно)

```bash
curl -X POST http://localhost:8080/scheduler/stop | jq
```

### Запустить снова

```bash
curl -X POST http://localhost:8080/scheduler/start | jq
```

## 7. Мониторинг в реальном времени

### Создай скрипт watch_status.sh

```bash
#!/bin/bash

# Мониторинг статуса каждые 10 секунд
watch -n 10 'curl -s http://localhost:8080/statistics | jq'
```

Или проще:

```bash
# Смотреть статус каждые 10 секунд
watch -n 10 "curl -s http://localhost:8080/statistics | jq '.total_accounts, .active_accounts, .average_warmup_stage'"
```

## 8. Типичный рабочий процесс

### День 1 - Добавление аккаунтов

```bash
# 1. Запустить сервис
python main.py

# В другом терминале:

# 2. Добавить аккаунты
curl -X POST http://localhost:8080/accounts/add \
  -H "Content-Type: application/json" \
  -d '{"session_id": "ses1", "phone_number": "+79991111111", "daily_activity_count": 3}'

# 3. Проверить, что добавились
curl http://localhost:8080/accounts | jq

# 4. Scheduler автоматически начнет прогрев через ~30 минут
# Или запустить вручную:
curl -X POST http://localhost:8080/accounts/1/warmup-now

# 5. Смотреть логи
tail -f logs/heat_up.log
```

### Ежедневный мониторинг

```bash
# Ежедневный отчет
curl http://localhost:8080/statistics/daily | jq

# Проверить health всех аккаунтов
for id in 1 2 3; do
  echo "=== Account $id ==="
  curl -s http://localhost:8080/accounts/$id/health | jq '.health_score, .health_status, .issues'
done

# Проверить, есть ли frozen аккаунты
curl -s http://localhost:8080/accounts | jq '.accounts[] | select(.is_frozen == true) | {id, session_id, phone_number}'
```

## 9. Обновление настроек аккаунта

```bash
ACCOUNT_ID=1

# Изменить частоту прогрева
curl -X POST http://localhost:8080/accounts/$ACCOUNT_ID/update \
  -H "Content-Type: application/json" \
  -d '{"daily_activity_count": 4}'

# Деактивировать аккаунт (прогрев остановится)
curl -X POST http://localhost:8080/accounts/$ACCOUNT_ID/update \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# Снять флаг frozen (после FloodWait)
curl -X POST http://localhost:8080/accounts/$ACCOUNT_ID/update \
  -H "Content-Type: application/json" \
  -d '{"is_frozen": false}'
```

## 10. Генерация/обновление данных

### Регенерировать личность

```bash
curl -X POST http://localhost:8080/accounts/$ACCOUNT_ID/generate-persona | jq
```

### Обновить список чатов

```bash
curl -X POST http://localhost:8080/accounts/$ACCOUNT_ID/refresh-chats | jq
```

## 11. Полезные команды для отладки

```bash
# Проверить, жив ли сервис
curl http://localhost:8080/health

# Проверить все endpoint'ы
curl http://localhost:8080/docs

# Посмотреть историю конкретной сессии (старый API)
curl http://localhost:8080/sessions/твой_session_id/history | jq

# Найти в логах конкретный аккаунт
grep "account_id.*: 1" logs/heat_up.log | tail -20

# Найти последние ошибки
grep ERROR logs/heat_up.log | tail -20

# Статистика по типам действий
grep "ACTION.*:" logs/heat_up.log | tail -50
```

## 12. Алерты и проблемы

### Если аккаунт заморожен (FloodWait)

```bash
# 1. Проверить health
curl http://localhost:8080/accounts/1/health | jq

# 2. Посмотреть, что произошло
grep "account.*1" logs/heat_up.log | grep -i "flood\|error" | tail -10

# 3. Подождать 24-48 часов

# 4. Снять флаг frozen
curl -X POST http://localhost:8080/accounts/1/update \
  -H "Content-Type: application/json" \
  -d '{"is_frozen": false}'

# 5. Возможно, снизить активность
curl -X POST http://localhost:8080/accounts/1/update \
  -H "Content-Type: application/json" \
  -d '{"daily_activity_count": 2}'
```

### Если scheduler не работает

```bash
# Проверить статус
curl http://localhost:8080/scheduler/status

# Перезапустить
curl -X POST http://localhost:8080/scheduler/stop
sleep 2
curl -X POST http://localhost:8080/scheduler/start
```

## 13. Dashboard в терминале (tmux)

Создай tmux сессию с 4 панелями:

```bash
# Запустить tmux
tmux new -s warmup

# Разделить на панели (Ctrl+B, затем %)
# Панель 1: Сервис
python main.py

# Панель 2: Логи в реальном времени (Ctrl+B, затем ")
tail -f logs/heat_up.log

# Панель 3: Статистика каждые 10 сек
watch -n 10 'curl -s http://localhost:8080/statistics | jq'

# Панель 4: Команды
# Здесь можешь вводить curl команды
```

## 14. Проверка что все работает

```bash
# 1. Сервис запущен
curl http://localhost:8080/health
# Ожидаем: {"status":"healthy",...}

# 2. Scheduler работает
curl http://localhost:8080/scheduler/status
# Ожидаем: {"is_running":true,...}

# 3. Аккаунты добавлены
curl http://localhost:8080/accounts
# Ожидаем: {"total":3,...}

# 4. Последние логи без критичных ошибок
tail -20 logs/heat_up.log

# 5. Запустить тестовый прогрев
curl -X POST http://localhost:8080/accounts/1/warmup-now

# 6. Через минуту проверить детали
curl http://localhost:8080/accounts/1 | jq '.recent_warmup_sessions[0]'
```

## Готово! 🎉

Теперь система:
- ✅ Автоматически прогревает аккаунты N раз в день
- ✅ Создает уникальные личности
- ✅ Находит релевантные чаты
- ✅ Имитирует естественное поведение
- ✅ Постепенно увеличивает активность (14 стадий)
- ✅ Логирует все действия
- ✅ Предоставляет метрики и health checks

**Следи за:**
- `logs/heat_up.log` - все события
- `/statistics/daily` - ежедневная сводка
- `/accounts/{id}/health` - здоровье каждого аккаунта

