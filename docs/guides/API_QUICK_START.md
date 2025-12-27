# 🚀 Heat Up API - Быстрый старт

## ✅ Готово к использованию

API для добавления аккаунтов в прогрев развернуто и защищено токеном аутентификации.

## 📍 Доступ

- **IP**: `116.203.112.192`
- **Порт**: `8080`
- **URL**: `http://116.203.112.192:8080`

## 🔑 Токен аутентификации

**Текущий токен:**
```
4YAVOYxInmPlIc5ccIKTeW1rWauMiWmBxisqw4exhwc
```

## 📝 Примеры запросов

### 1. Проверка здоровья сервиса (без токена)

```bash
curl http://116.203.112.192:8080/health
```

**Ответ:**
```json
{"status":"healthy","telegram_client":true,"llm_agent":true}
```

### 2. Добавление аккаунта (требует токен)

#### Минимальный запрос

```bash
curl -X POST http://116.203.112.192:8080/accounts/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 4YAVOYxInmPlIc5ccIKTeW1rWauMiWmBxisqw4exhwc" \
  -d '{
    "session_id": "123456"
  }'
```

#### Полный запрос

```bash
curl -X POST http://116.203.112.192:8080/accounts/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 4YAVOYxInmPlIc5ccIKTeW1rWauMiWmBxisqw4exhwc" \
  -d '{
    "session_id": "123456",
    "phone_number": "+79001234567",
    "country": "Russia"
  }'
```

#### Python пример

```python
import requests

API_URL = "http://116.203.112.192:8080"
TOKEN = "4YAVOYxInmPlIc5ccIKTeW1rWauMiWmBxisqw4exhwc"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

data = {
    "session_id": "123456"
}

response = requests.post(
    f"{API_URL}/accounts/add",
    headers=headers,
    json=data
)

print(response.status_code)
print(response.json())
```

## 📊 Что происходит при добавлении аккаунта

Система автоматически:

1. **Получает информацию** о стране из Admin API по session_id
2. **Генерирует уникальную персону** через LLM (имя, интересы, город)
3. **Определяет активность** (min/max прогревов в день на основе персоны)
4. **Ищет релевантные чаты** для прогрева (каналы, группы по интересам)
5. **Сохраняет в БД** с задержкой до первого прогрева (0-10 часов)

## ✅ Успешный ответ

```json
{
  "success": true,
  "message": "Account added successfully with ID 72",
  "data": {
    "id": 72,
    "session_id": "123456",
    "phone_number": "+79632069531",
    "created_at": "2025-11-11 11:44:20",
    "warmup_stage": 1,
    "country": "Russia",
    "persona_generated": true,
    "persona_name": "Людмила Тарасенко",
    "chats_discovered": 20,
    "activity_range": "3-5",
    "warmup_start_delay_until": "2025-11-11T17:29:48.156759"
  }
}
```

## ❌ Ошибки

### 403 - Не указан токен или токен неверный

```bash
curl -X POST http://116.203.112.192:8080/accounts/add \
  -H "Content-Type: application/json" \
  -d '{"session_id": "123456"}'
```

**Ответ:**
```json
{
  "detail": "Not authenticated"
}
```

### 401 - Неверный токен

```json
{
  "detail": "Invalid or expired API token"
}
```

### 409 - Аккаунт уже существует

```json
{
  "detail": "Session ID '123456' already exists in database (Account ID: 1, Phone: +79001234567)"
}
```

## 🔐 Управление токенами

### Создать новый токен

```bash
cd /root/heat_up
python3 manage_tokens.py create --name "production" --description "Production API"
```

### Посмотреть все токены

```bash
python3 manage_tokens.py list
```

### Отозвать токен

```bash
python3 manage_tokens.py revoke <token>
```

## 📖 Параметры запроса

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `session_id` | string | ✅ | ID Telegram сессии |
| `phone_number` | string | ❌ | Номер телефона |
| `country` | string | ❌ | Страна (по умолчанию: "Russia") |
| `min_daily_activity` | int | ❌ | Мин. прогревов (2-10, авто LLM) |
| `max_daily_activity` | int | ❌ | Макс. прогревов (2-10, авто LLM) |
| `provider` | string | ❌ | Провайдер |
| `proxy_id` | int | ❌ | ID прокси |

## 🔄 Автоматическое управление

После добавления аккаунта:

- ✅ Автоматически создается уникальная персона
- ✅ Подбираются релевантные чаты для прогрева
- ✅ Аккаунт добавляется в планировщик
- ✅ Прогрев начнется автоматически через 0-10 часов
- ✅ Прогрев выполняется 3-6 раз в день (зависит от персоны)

## 🎯 Тестирование

### Проверка без токена (должен вернуть 403)

```bash
curl -v -X POST http://116.203.112.192:8080/accounts/add \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test"}'
```

### Проверка с токеном (должен вернуть 200)

```bash
curl -v -X POST http://116.203.112.192:8080/accounts/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 4YAVOYxInmPlIc5ccIKTeW1rWauMiWmBxisqw4exhwc" \
  -d '{"session_id": "test_token_' $(date +%s) '"}'
```

## 📞 Поддержка

- Логи: `docker logs heat_up_service`
- Перезапуск: `docker restart heat_up_service`
- Полная документация: `API_TOKEN_GUIDE.md`

