# Руководство по использованию системы прогрева аккаунтов

## Обзор

Система прогрева аккаунтов Telegram автоматически имитирует естественное поведение пользователей для постепенной подготовки аккаунтов к работе. Каждый аккаунт получает уникальную личность и прогревается в течение 14 дней с постепенным увеличением активности.

## Архитектура

### Компоненты

1. **PersonaAgent** - Генерирует уникальную личность для каждого аккаунта
2. **SearchAgent** - Находит релевантные чаты/каналы для личности
3. **ActionPlannerAgent** - Планирует действия с учетом стадии прогрева
4. **ActionExecutor** - Выполняет запланированные действия
5. **WarmupScheduler** - Автоматически запускает прогрев N раз в день
6. **WarmupMonitor** - Мониторинг и статистика

### Стадии прогрева (1-14 дней)

- **День 1**: Только настройка профиля
- **День 2-3**: Заполнение профиля, вступление в 1-2 канала
- **День 4-7**: Чтение, реакции, сообщения ботам
- **День 8-14**: Активное участие, создание групп, форварды

## Быстрый старт

### 1. Запуск сервиса

```bash
# Активировать виртуальное окружение
source venv/bin/activate

# Запустить сервис
python main.py
```

Scheduler запустится автоматически, если `SCHEDULER_ENABLED=true` в `.env`

### 2. Добавление аккаунта

```bash
curl -X POST http://localhost:8080/accounts/add \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your_telegram_session_uid",
    "phone_number": "+79991234567",
    "country": "Russia",
    "daily_activity_count": 3
  }'
```

**Параметры:**
- `session_id` - UID сессии из основной системы
- `phone_number` - номер телефона аккаунта
- `country` - страна (опционально, определится по номеру)
- `daily_activity_count` - сколько раз в день прогревать (2-5)

### 3. Генерация личности

После добавления аккаунта система автоматически создаст личность при первом прогреве. Но можно сделать это вручную:

```bash
curl -X POST http://localhost:8080/accounts/{account_id}/generate-persona
```

Личность включает:
- Имя и фамилия (соответствуют культуре страны)
- Возраст, профессия, город
- Интересы и черты характера
- Стиль общения

### 4. Поиск релевантных чатов

```bash
curl -X POST http://localhost:8080/accounts/{account_id}/refresh-chats
```

SearchAgent найдет 10-20 чатов, релевантных интересам личности, используя TGStat API и LLM-ранжирование.

### 5. Мониторинг

#### Статус scheduler

```bash
curl http://localhost:8080/scheduler/status
```

#### Список аккаунтов

```bash
curl http://localhost:8080/accounts
```

#### Детали аккаунта

```bash
curl http://localhost:8080/accounts/{account_id}
```

Вернет:
- Основную информацию
- Личность
- Найденные чаты
- Последние 10 сессий прогрева

#### Здоровье аккаунта

```bash
curl http://localhost:8080/accounts/{account_id}/health
```

Вернет:
- Health score (0-100)
- Проблемы (если есть)
- Рекомендации

#### Общая статистика

```bash
curl http://localhost:8080/statistics
```

#### Ежедневный отчет

```bash
curl http://localhost:8080/statistics/daily
```

## Управление scheduler

### Запуск

```bash
curl -X POST http://localhost:8080/scheduler/start
```

### Остановка

```bash
curl -X POST http://localhost:8080/scheduler/stop
```

### Проверка статуса

```bash
curl http://localhost:8080/scheduler/status
```

## Ручной прогрев

Для немедленного прогрева аккаунта (вне расписания):

```bash
curl -X POST http://localhost:8080/accounts/{account_id}/warmup-now
```

## Обновление настроек аккаунта

```bash
curl -X POST http://localhost:8080/accounts/{account_id}/update \
  -H "Content-Type: application/json" \
  -d '{
    "daily_activity_count": 5,
    "warmup_stage": 3
  }'
```

**Параметры:**
- `daily_activity_count` - частота прогрева (2-5)
- `warmup_stage` - текущая стадия прогрева (1-14+)
- `is_active` - активен ли аккаунт
- `is_frozen` - заморожен ли (FloodWait)
- `is_banned` - забанен ли

## Конфигурация

### Основные настройки (`.env`)

```env
# Scheduler
SCHEDULER_ENABLED=true
SCHEDULER_CHECK_INTERVAL=1800  # 30 минут

# Прогрев
WARMUP_MAX_STAGE=14
DEFAULT_DAILY_ACTIVITY_COUNT=3

# Search
SEARCH_CHATS_PER_PERSONA=20

# OpenAI
OPENAI_API_KEY=your_key

# TGStat
TGSTAT_API_TOKEN=your_token
```

## Рекомендации по прогреву

### Зеленые флаги (что делать)

✅ Постепенное увеличение активности день за днём
✅ Разнообразие действий (не только join → read)
✅ Участие в диалогах (ответы на вопросы других)
✅ Реакции на сообщения
✅ Паузы между действиями разной длины
✅ Уникальные сообщения для каждого чата
✅ Естественное поведение как у обычного человека

### Красные флаги (избегать)

❌ Отправка одинаковых сообщений в разные чаты
❌ Слишком много действий сразу после долгой паузы
❌ Вступление в более 3 чатов за одну сессию
❌ Отправка сообщений чаще 1 раза в 3 часа
❌ Массовая рассылка в первые дни
❌ Использование шаблонных текстов

## Обработка ошибок

### FloodWait

Если система обнаружит FloodWait:
1. Аккаунт автоматически помечается как `is_frozen=true`
2. Прогрев останавливается
3. Рекомендуется подождать 24-48 часов
4. Вручную снять флаг через `/accounts/{id}/update`

### Рекомендации при FloodWait

1. Проверить `daily_activity_count` - возможно, слишком частый прогрев
2. Проверить health score - может быть проблема с качеством действий
3. Убедиться, что аккаунты не используются для рассылок параллельно с прогревом

## Логирование

Все логи записываются в `logs/heat_up.log` и содержат:
- Все действия scheduler
- Генерацию личностей
- Поиск чатов
- Выполнение действий
- Ошибки и предупреждения

## API Endpoints

### Управление аккаунтами

- `POST /accounts/add` - Добавить аккаунт
- `GET /accounts` - Список аккаунтов
- `GET /accounts/{id}` - Детали аккаунта
- `POST /accounts/{id}/generate-persona` - Сгенерировать личность
- `POST /accounts/{id}/refresh-chats` - Обновить чаты
- `POST /accounts/{id}/warmup-now` - Запустить прогрев сейчас
- `POST /accounts/{id}/update` - Обновить настройки
- `DELETE /accounts/{id}` - Деактивировать аккаунт
- `GET /accounts/{id}/health` - Проверить здоровье

### Scheduler

- `POST /scheduler/start` - Запустить
- `POST /scheduler/stop` - Остановить
- `GET /scheduler/status` - Статус

### Статистика

- `GET /statistics` - Общая статистика
- `GET /statistics/daily` - Ежедневный отчет

### Совместимость со старым API

- `POST /warmup/{session_id}` - Разовый прогрев (background)
- `POST /warmup-sync/{session_id}` - Разовый прогрев (sync)
- `GET /sessions/{session_id}/history` - История сессии

## Примеры использования

### Полный цикл добавления и прогрева

```bash
# 1. Добавить аккаунт
ACCOUNT_RESPONSE=$(curl -X POST http://localhost:8080/accounts/add \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc123",
    "phone_number": "+79991234567",
    "daily_activity_count": 3
  }')

ACCOUNT_ID=$(echo $ACCOUNT_RESPONSE | jq -r '.data.id')

# 2. Сгенерировать личность
curl -X POST http://localhost:8080/accounts/$ACCOUNT_ID/generate-persona

# 3. Найти релевантные чаты
curl -X POST http://localhost:8080/accounts/$ACCOUNT_ID/refresh-chats

# 4. Запустить первый прогрев
curl -X POST http://localhost:8080/accounts/$ACCOUNT_ID/warmup-now

# 5. Проверить результат
curl http://localhost:8080/accounts/$ACCOUNT_ID
```

### Массовое добавление аккаунтов

```bash
# accounts.json
[
  {"session_id": "ses1", "phone_number": "+79991111111"},
  {"session_id": "ses2", "phone_number": "+79992222222"},
  {"session_id": "ses3", "phone_number": "+79993333333"}
]

# Добавить все
for account in $(cat accounts.json | jq -c '.[]'); do
  curl -X POST http://localhost:8080/accounts/add \
    -H "Content-Type: application/json" \
    -d "$account"
done
```

## Troubleshooting

### Scheduler не запускается

1. Проверить `.env`: `SCHEDULER_ENABLED=true`
2. Проверить логи: `tail -f logs/heat_up.log`
3. Проверить статус: `curl http://localhost:8080/scheduler/status`

### Аккаунт не прогревается

1. Проверить `is_active`: `curl http://localhost:8080/accounts/{id}`
2. Проверить `is_frozen` или `is_banned`
3. Проверить `last_warmup_date` - может быть, еще рано
4. Проверить health: `curl http://localhost:8080/accounts/{id}/health`

### Высокая частота ошибок

1. Снизить `daily_activity_count`
2. Проверить, не используются ли аккаунты параллельно для рассылок
3. Убедиться, что не превышены лимиты Telegram
4. Проверить настройки прокси

## Best Practices

1. **Начинайте медленно**: Для новых аккаунтов используйте `daily_activity_count=2-3`
2. **Мониторьте health**: Регулярно проверяйте `/accounts/{id}/health`
3. **Используйте разные личности**: Не создавайте однотипных пользователей
4. **Не торопитесь**: Дайте аккаунтам пройти все 14 дней прогрева
5. **Следите за логами**: `tail -f logs/heat_up.log`
6. **Проверяйте статистику**: Используйте `/statistics/daily` для оценки эффективности

## Поддержка

При возникновении проблем:
1. Проверьте логи в `logs/heat_up.log`
2. Проверьте health конкретного аккаунта
3. Проверьте общую статистику системы
4. Убедитесь, что все зависимости установлены: `pip install -r requirements.txt`

