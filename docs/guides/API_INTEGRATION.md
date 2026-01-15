# Heat Up API Documentation

API для интеграции с системой прогрева Telegram-аккаунтов.

## Base URL

```
https://heatup.knyazservice.com
```

## Авторизация

Все запросы требуют Bearer токен в заголовке:

```
Authorization: Bearer <API_TOKEN>
```

Токен выдаётся администратором системы.

---

## Endpoints

### 1. Добавить сессию в прогрев

Добавляет новую сессию в систему прогрева. Автоматически генерирует персону и находит релевантные чаты.

```
POST /accounts/add
```

#### Request

**Headers:**
```
Authorization: Bearer <API_TOKEN>
Content-Type: application/json
```

**Body:**
```json
{
  "session_id": "27190"
}
```

#### Параметры

| Поле | Тип | Обязательный | Описание |
|------|-----|--------------|----------|
| `session_id` | string | ✅ | ID сессии из Admin API |
| `phone_number` | string | ❌ | Номер телефона (авто-генерируется) |
| `country` | string | ❌ | Страна (авто из Admin API) |
| `min_daily_activity` | int (2-10) | ❌ | Мин. прогревов в день (авто LLM) |
| `max_daily_activity` | int (2-10) | ❌ | Макс. прогревов в день (авто LLM) |
| `provider` | string | ❌ | Провайдер сессии |
| `proxy_id` | int | ❌ | ID прокси |

#### Response (Success)

**HTTP 200**
```json
{
  "success": true,
  "message": "Account added successfully with ID 312",
  "data": {
    "id": 312,
    "session_id": "27190",
    "phone_number": "+79081431781",
    "created_at": "2026-01-15 08:03:32",
    "warmup_stage": 1,
    "first_warmup_date": "2026-01-15 08:03:32.433788",
    "last_warmup_date": null,
    "min_daily_activity": 3,
    "max_daily_activity": 6,
    "total_warmups": 0,
    "total_actions": 0,
    "joined_channels_count": 0,
    "sent_messages_count": 0,
    "is_active": 1,
    "country": "Ukraine",
    "account_type": "warmup",
    "can_initiate_dm": 1,
    "persona_generated": true,
    "persona_name": "Анна Тарасенко",
    "chats_discovered": 20,
    "activity_range": "3-6"
  }
}
```

#### Response (Error - Duplicate)

**HTTP 409**
```json
{
  "detail": "Session ID '27190' already exists in database (Account ID: 312, Phone: +79081431781)"
}
```

#### Response (Error - Auth)

**HTTP 401**
```json
{
  "detail": "Invalid or expired API token"
}
```

---

### 2. Получить лучшую прогретую сессию

Возвращает наиболее прогретую сессию, готовую к использованию.

```
GET /accounts/best-warmed
```

#### Критерии отбора

- `status = 0` в Admin API (активная)
- `is_premium = false` в Admin API (не премиум)
- Не забанена, не заморожена, не удалена
- Сортировка по `warmup_stage` DESC (самая прогретая первая)

#### Query Parameters

| Параметр | Тип | Описание |
|----------|-----|----------|
| `country` | string | Фильтр по одной стране (например: `Ukraine`) |
| `countries` | string | Фильтр по нескольким странам через запятую (например: `Ukraine,Russia`) |
| `exclude_countries` | string | Исключить страны через запятую (например: `Iran,Russia`) |

#### Request

**Headers:**
```
Authorization: Bearer <API_TOKEN>
```

**Примеры:**

```bash
# Без фильтров - вернёт самую прогретую из всех
GET /accounts/best-warmed

# Только Украина
GET /accounts/best-warmed?country=Ukraine

# Украина или Россия
GET /accounts/best-warmed?countries=Ukraine,Russia

# Все кроме России и Ирана
GET /accounts/best-warmed?exclude_countries=Russia,Iran
```

#### Response (Success)

**HTTP 200**
```json
{
  "success": true,
  "account": {
    "id": 100,
    "session_id": "27167",
    "phone_number": "380934578018",
    "country": "Ukraine",
    "warmup_stage": 14,
    "first_warmup_date": "2025-12-26 10:49:32.618650",
    "total_warmups": 108,
    "total_actions": 1057,
    "joined_channels_count": 2,
    "telegram_id": 8116891095,
    "status": 0,
    "is_premium": false
  }
}
```

#### Response (Error - Not Found)

**HTTP 404**
```json
{
  "detail": "No account found with status=0 and is_premium=false"
}
```

---

### 3. Health Check

Проверка работоспособности сервиса.

```
GET /health
```

#### Response

**HTTP 200**
```json
{
  "status": "healthy",
  "telegram_client": true,
  "llm_agent": true
}
```

---

## Примеры интеграции

### Python (httpx)

```python
import httpx

HEATUP_URL = "https://heatup.knyazservice.com"
HEATUP_TOKEN = "your_api_token_here"

headers = {"Authorization": f"Bearer {HEATUP_TOKEN}"}


async def add_session(session_id: int):
    """Добавить сессию в прогрев"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{HEATUP_URL}/accounts/add",
            headers=headers,
            json={"session_id": str(session_id)}
        )
        return response.json()


async def get_best_session(country: str = None, exclude: list = None):
    """Получить лучшую прогретую сессию"""
    params = {}
    if country:
        params["country"] = country
    if exclude:
        params["exclude_countries"] = ",".join(exclude)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{HEATUP_URL}/accounts/best-warmed",
            headers=headers,
            params=params
        )
        return response.json()


# Примеры использования
result = await add_session(27190)
best = await get_best_session(country="Ukraine")
best_no_russia = await get_best_session(exclude=["Russia", "Iran"])
```

### curl

```bash
# Добавить сессию
curl -X POST "https://heatup.knyazservice.com/accounts/add" \
  -H "Authorization: Bearer $HEATUP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "27190"}'

# Получить лучшую украинскую сессию
curl "https://heatup.knyazservice.com/accounts/best-warmed?country=Ukraine" \
  -H "Authorization: Bearer $HEATUP_TOKEN"

# Получить лучшую сессию кроме России
curl "https://heatup.knyazservice.com/accounts/best-warmed?exclude_countries=Russia" \
  -H "Authorization: Bearer $HEATUP_TOKEN"
```

---

## Коды ответов

| Код | Описание |
|-----|----------|
| 200 | Успешный запрос |
| 401 | Неверный или отсутствующий токен |
| 404 | Ресурс не найден |
| 409 | Конфликт (дубликат сессии) |
| 500 | Внутренняя ошибка сервера |

---

## Доступные страны

Основные страны в системе прогрева:
- `Russia`
- `Ukraine`
- `Iran`
- `Kazakhstan`

*Названия стран регистронезависимые (Ukraine = ukraine = UKRAINE)*
