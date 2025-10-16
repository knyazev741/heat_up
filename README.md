# Heat Up - Telegram Session Warmup Service

Автоматизированный сервис для "прогрева" новых Telegram-аккаунтов через естественное поведение пользователя, генерируемое с помощью LLM.

## 🎯 Назначение

Heat Up получает ID сессии Telegram и автоматически выполняет серию естественных действий нового пользователя:
- Присоединение к 2-4 разнообразным каналам
- Просмотр сообщений в каналах
- Естественные паузы между действиями
- Уникальная последовательность действий каждый раз (через LLM)

## 🏗️ Архитектура

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /warmup/{session_id}
       ▼
┌─────────────────┐
│  FastAPI Server │
└────────┬────────┘
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
┌────────┐ ┌──────────────┐
│  LLM   │ │   Telegram   │
│ Agent  │ │  API Client  │
└────────┘ └──────────────┘
    │              │
    └──────┬───────┘
           ▼
    ┌──────────────┐
    │   Executor   │
    └──────────────┘
```

## 📋 Возможности

- **LLM-генерация действий**: 🆕 **DeepSeek Chat** генерирует уникальные естественные последовательности действий (89% экономии на API!)
- **🆕 Реальные каналы**: 30+ реальных, проверенных Telegram-каналов из TGStat
- **🆕 История сессий**: Отслеживание действий каждой сессии в SQLite
- **🆕 Динамические промпты**: Адаптация поведения для новых и возвращающихся пользователей
- **Разнообразие каналов**: Каналы разных категорий (новости, технологии, развлечения и т.д.)
- **Естественные задержки**: Случайные паузы между действиями для имитации человека
- **Два режима работы**:
  - Асинхронный (`/warmup/{session_id}`) - быстрый ответ, выполнение в фоне
  - Синхронный (`/warmup-sync/{session_id}`) - ожидание завершения, полный отчет
- **Детальное логирование**: Отслеживание каждого действия
- **Обработка ошибок**: Graceful handling с fallback-планами

## 🚀 Быстрый старт

> **📦 Развертывание на сервере?** См. **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - полное руководство по установке на production сервере (Docker, systemd, nginx).

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка окружения

Создайте файл `.env`:

```env
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
TELEGRAM_API_BASE_URL=http://your-telegram-api:8000
TELEGRAM_API_KEY=optional-api-key
LOG_LEVEL=INFO
```

> **Note**: Система использует DeepSeek API (OpenAI-совместимый) для генерации действий.
> См. [DEEPSEEK_MIGRATION.md](docs/guides/DEEPSEEK_MIGRATION.md) для подробностей.

### 3. Запуск сервиса

```bash
# Режим разработки
python main.py

# Или через uvicorn
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

## 📡 API Endpoints

### `POST /warmup/{session_id}`

Асинхронный прогрев сессии (возвращает план и выполняет в фоне).

**Request:**
```bash
curl -X POST "http://localhost:8080/warmup/abc123xyz789"
```

**Response:**
```json
{
  "session_id": "abc123xyz789",
  "status": "started",
  "message": "Warmup initiated with 5 actions",
  "action_plan": [
    {
      "action": "join_channel",
      "channel_username": "@telegram",
      "reason": "Join official updates channel"
    },
    {
      "action": "read_messages",
      "channel_username": "@telegram",
      "duration_seconds": 8,
      "reason": "Browse recent posts"
    }
  ]
}
```

### `POST /warmup-sync/{session_id}`

Синхронный прогрев (ждет завершения и возвращает полный отчет).

**Request:**
```bash
curl -X POST "http://localhost:8080/warmup-sync/abc123xyz789"
```

**Response:**
```json
{
  "session_id": "abc123xyz789",
  "status": "completed",
  "message": "Warmup completed: 5/5 actions successful",
  "action_plan": [...],
  "execution_summary": {
    "session_id": "abc123xyz789",
    "total_actions": 5,
    "successful_actions": 5,
    "failed_actions": 0,
    "joined_channels": ["@telegram", "@durov"],
    "results": [...]
  }
}
```

### `GET /health`

Проверка состояния сервиса.

```bash
curl http://localhost:8080/health
```

### `GET /sessions/{session_id}/history`

**🆕 Новый эндпоинт:** Получение истории действий сессии.

**Request:**
```bash
curl "http://localhost:8080/sessions/abc123xyz789/history?days=30"
```

**Response:**
```json
{
  "session_id": "abc123xyz789",
  "summary": {
    "is_new": false,
    "total_actions": 15,
    "joined_channels": ["@durov", "@telegram", "@crypto"],
    "last_activity": "2024-01-10T12:34:56"
  },
  "history": [
    {
      "id": 1,
      "action_type": "join_channel",
      "action_data": {"channel_username": "@durov"},
      "timestamp": "2024-01-10T12:30:00"
    }
  ]
}
```

## 🔧 Технические детали

### 🆕 TGStat и История Сессий

Подробная документация по новым функциям: **[TGSTAT_INTEGRATION.md](docs/guides/TGSTAT_INTEGRATION.md)**

- Реальные каналы из TGStat
- SQLite база данных для истории
- Динамические промпты для LLM
- Автоматическая очистка старых записей

### Telegram API интеграция

Проект использует **pylogram 0.12.3** (Layer 201) для корректного взаимодействия с Telegram API через RPC вызовы. Все TL (Type Language) запросы формируются через `repr()` строки pylogram объектов, что обеспечивает совместимость с сервером.

Пример invoke запроса:
```json
{
  "method": "invoke",
  "params": {
    "query": "pylogram.raw.functions.messages.GetDialogs(offset_date=0, offset_id=0, offset_peer=pylogram.raw.types.InputPeerEmpty(), limit=20, hash=0)",
    "retries": 10,
    "timeout": 15
  }
}
```

### Каналы (`config.py`)

Список каналов хранится в `CHANNEL_POOL`. Вы можете добавить свои:

```python
CHANNEL_POOL = [
    {"username": "@yourchannel", "description": "Your channel description"},
    # ...
]
```

### Таймауты и задержки

```python
ACTION_DELAYS = {
    "min_between_actions": 3,      # Минимальная пауза между действиями
    "max_between_actions": 10,     # Максимальная пауза
    "min_read_time": 5,            # Минимальное время чтения
    "max_read_time": 15,           # Максимальное время чтения
}
```

## 📁 Структура проекта

```
heat_up/
├── main.py                    # FastAPI приложение
├── config.py                  # Конфигурация и настройки
├── telegram_client.py         # Клиент для Telegram API
├── llm_agent.py               # LLM-агент для генерации действий
├── executor.py                # Исполнитель действий
├── database.py                # 🆕 Управление базой данных SQLite
├── tgstat_fetcher.py          # 🆕 Загрузка каналов из TGStat
├── channels_data.json         # 🆕 Кэш реальных каналов
├── sessions.db                # 🆕 База данных истории (создается автоматически)
├── requirements.txt           # Зависимости Python
├── openapi.json               # OpenAPI спецификация Telegram API
├── README.md                  # Документация
└── TGSTAT_INTEGRATION.md      # 🆕 Документация по новым функциям
```

## 🎭 Типы действий

1. **join_channel** - Присоединение к каналу
   - Параметры: `channel_username`
   
2. **read_messages** - Просмотр сообщений
   - Параметры: `channel_username`, `duration_seconds`
   
3. **idle** - Пауза/отдых
   - Параметры: `duration_seconds`

## 🔐 Безопасность

- Все API-ключи хранятся в `.env` (не коммитить!)
- Валидация входных данных
- Ограничения на длительность действий
- Graceful error handling

## 📊 Логирование

Сервис логирует все действия:

```
2024-10-10 12:00:00 - INFO - Received warmup request for session: abc123xyz789
2024-10-10 12:00:01 - INFO - Generated 5 actions for session abc123xyz789
2024-10-10 12:00:02 - INFO - [1/5] Executing: join_channel - Join official channel
2024-10-10 12:00:05 - INFO - Successfully joined @telegram
...
```

## 🧪 Примеры использования

### Python

```python
import httpx
import asyncio

async def warmup_session(session_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8080/warmup/{session_id}"
        )
        return response.json()

result = asyncio.run(warmup_session("abc123xyz789"))
print(result)
```

### cURL

```bash
# Асинхронный режим
curl -X POST http://localhost:8080/warmup/abc123xyz789

# Синхронный режим с полным отчетом
curl -X POST http://localhost:8080/warmup-sync/abc123xyz789

# С кастомным Telegram API
curl -X POST http://localhost:8080/warmup/abc123xyz789 \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_api_base_url": "http://custom-api:8000",
    "telegram_api_key": "your-key"
  }'
```

## 🔄 Workflow

1. **Запрос** → Клиент отправляет `session_id`
2. **Генерация** → LLM создает уникальный план действий (3-7 шагов)
3. **Валидация** → Проверка и санитизация действий
4. **Выполнение** → Последовательное выполнение с естественными задержками
5. **Отчет** → Возврат результатов с деталями успеха/ошибок

## 🐛 Troubleshooting

### LLM не генерирует действия
- Проверьте `OPENAI_API_KEY` в `.env`
- Убедитесь в наличии интернета
- Проверьте лимиты API

### Ошибки Telegram API
- Проверьте `TELEGRAM_API_BASE_URL`
- Убедитесь, что сессия существует и активна
- Проверьте права доступа

### Действия не выполняются
- Проверьте логи: `LOG_LEVEL=DEBUG`
- Убедитесь, что каналы существуют
- Проверьте сетевое соединение

## 📈 Будущие улучшения

- [ ] Поддержка отправки сообщений
- [ ] Реакции на посты
- [x] **Сохранение истории прогревов** ✅
- [x] **Реальные каналы из TGStat** ✅
- [x] **Адаптивное поведение на основе истории** ✅
- [ ] Метрики и мониторинг
- [ ] WebSocket для real-time обновлений
- [ ] Batch processing нескольких сессий
- [ ] Кастомные сценарии поведения
- [ ] Периодическая валидация существования каналов

## 📄 Лицензия

MIT

## 🤝 Вклад

Приветствуются pull requests и issue reports!

