# 🔐 API Token Authentication Guide

## Обзор

API для добавления аккаунтов в прогрев теперь защищено токенами аутентификации.

## 🔑 Управление токенами

### Создание нового токена

```bash
python3 manage_tokens.py create --name "production" --description "Production API access"
```

**Важно:** Токен показывается только один раз! Сохраните его в безопасном месте.

### Просмотр всех токенов

```bash
python3 manage_tokens.py list
```

### Отзыв токена

```bash
python3 manage_tokens.py revoke <token>
```

## 📍 Доступ к API

### Базовая информация

- **IP сервера:** `116.203.112.192`
- **Порт:** `8080`
- **Базовый URL:** `http://116.203.112.192:8080`

### Endpoints

#### 1. Health Check (без токена)
```bash
curl http://116.203.112.192:8080/health
```

#### 2. Добавление аккаунта (требует токен)
```bash
curl -X POST http://116.203.112.192:8080/accounts/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "session_id": "123456",
    "phone_number": "+79001234567",
    "country": "Russia"
  }'
```

## 📝 Примеры использования

### Python

```python
import requests

API_URL = "http://116.203.112.192:8080"
API_TOKEN = "4YAVOYxInmPlIc5ccIKTeW1rWauMiWmBxisqw4exhwc"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

data = {
    "session_id": "123456",
    "phone_number": "+79001234567",
    "country": "Russia"
}

response = requests.post(
    f"{API_URL}/accounts/add",
    headers=headers,
    json=data
)

print(response.json())
```

### cURL

```bash
# Полный пример с реальным токеном
TOKEN="4YAVOYxInmPlIc5ccIKTeW1rWauMiWmBxisqw4exhwc"

curl -X POST http://116.203.112.192:8080/accounts/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "session_id": "123456",
    "phone_number": "+79001234567",
    "country": "Russia"
  }'
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const API_URL = 'http://116.203.112.192:8080';
const API_TOKEN = '4YAVOYxInmPlIc5ccIKTeW1rWauMiWmBxisqw4exhwc';

const addAccount = async (sessionId, phoneNumber, country = 'Russia') => {
  try {
    const response = await axios.post(
      `${API_URL}/accounts/add`,
      {
        session_id: sessionId,
        phone_number: phoneNumber,
        country: country
      },
      {
        headers: {
          'Authorization': `Bearer ${API_TOKEN}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    console.log('Account added:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error adding account:', error.response?.data || error.message);
    throw error;
  }
};

// Использование
addAccount('123456', '+79001234567', 'Russia');
```

## 🔍 Структура запроса

### AddAccountRequest

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `session_id` | string | ✅ | Telegram session UID |
| `phone_number` | string | ❌ | Номер телефона (опционально) |
| `country` | string | ❌ | Страна (по умолчанию: "Russia") |
| `min_daily_activity` | int | ❌ | Мин. прогревов в день (2-10, авто-генерация LLM) |
| `max_daily_activity` | int | ❌ | Макс. прогревов в день (2-10, авто-генерация LLM) |
| `provider` | string | ❌ | Провайдер |
| `proxy_id` | int | ❌ | ID прокси |

### Пример минимального запроса

```json
{
  "session_id": "123456"
}
```

Система автоматически:
- Получит страну из Admin API по session_id
- Сгенерирует уникальную персону через LLM
- Определит min/max активность на основе персоны
- Найдет релевантные чаты для прогрева

## 🔐 Безопасность

### Хранение токенов

Токены хранятся в файле `data/api_tokens.json` в хешированном виде (SHA-256).

**Важно:**
- Никогда не коммитьте токены в репозиторий
- Используйте переменные окружения для хранения токенов
- Регулярно обновляйте токены
- Отзывайте неиспользуемые токены

### Проверка доступа

При каждом запросе:
1. Токен проверяется по хешу
2. Обновляется статистика использования
3. Записывается время последнего использования

## 📊 Статистика использования токенов

```bash
# Посмотреть статистику по всем токенам
python3 manage_tokens.py list
```

Вывод покажет:
- Имя токена
- Хеш (первые 16 символов)
- Описание
- Дата создания
- Последнее использование
- Количество использований

## ❌ Обработка ошибок

### 401 Unauthorized
Токен недействителен или отсутствует:
```json
{
  "detail": "Invalid or expired API token"
}
```

### 409 Conflict
Аккаунт уже существует:
```json
{
  "detail": "Session ID '123456' already exists in database (Account ID: 1, Phone: +79001234567)"
}
```

### 500 Internal Server Error
Ошибка сервера (проверьте логи):
```bash
docker logs heat_up_service
```

## 🧪 Тестирование

### Проверка здоровья сервиса (без токена)

```bash
curl http://116.203.112.192:8080/health
```

### Проверка с неверным токеном

```bash
curl -X POST http://116.203.112.192:8080/accounts/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid_token" \
  -d '{"session_id": "123456"}'
```

Ожидаемый ответ: `401 Unauthorized`

### Проверка с правильным токеном

```bash
curl -X POST http://116.203.112.192:8080/accounts/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 4YAVOYxInmPlIc5ccIKTeW1rWauMiWmBxisqw4exhwc" \
  -d '{
    "session_id": "test123",
    "phone_number": "+79001234567"
  }'
```

## 🔄 Перезапуск сервиса

После изменения конфигурации:

```bash
cd /root/heat_up
docker-compose restart
```

## 📞 Текущий токен

**Токен по умолчанию:**
```
4YAVOYxInmPlIc5ccIKTeW1rWauMiWmBxisqw4exhwc
```

**Использование:**
```bash
export HEAT_UP_TOKEN="4YAVOYxInmPlIc5ccIKTeW1rWauMiWmBxisqw4exhwc"

curl -X POST http://116.203.112.192:8080/accounts/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $HEAT_UP_TOKEN" \
  -d '{
    "session_id": "123456",
    "phone_number": "+79001234567"
  }'
```

