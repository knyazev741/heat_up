# Telegram TL Query Examples

Примеры использования `telegram_tl_helpers.py` для создания правильных TL запросов.

## 📋 Формат запросов

Все invoke запросы должны использовать **repr() строки pylogram объектов**, а не JSON.

### ✅ Правильно:
```json
{
  "method": "invoke",
  "params": {
    "query": "pylogram.raw.functions.messages.GetDialogs(offset_date=0, offset_id=0, offset_peer=pylogram.raw.types.InputPeerEmpty(), limit=20, hash=0)"
  }
}
```

### ❌ Неправильно:
```json
{
  "method": "invoke",
  "params": {
    "query": "{\"_\": \"messages.getDialogs\", \"offset_date\": 0, ...}"
  }
}
```

---

## 🔧 Примеры использования helpers

### 1. GetDialogs - получить список чатов

```python
from telegram_tl_helpers import make_get_dialogs_query

# Получить 20 диалогов
query = make_get_dialogs_query(limit=20)
# Result: "pylogram.raw.functions.messages.GetDialogs(...)"

# Использование в запросе
await telegram_client.get_dialogs(session_id="17977", limit=20)
```

**Что возвращает:**
- `dialogs` - список диалогов
- `messages` - последние сообщения
- `chats` - информация о чатах
- `users` - информация о пользователях

---

### 2. ResolveUsername - получить инфо о канале/пользователе

```python
from telegram_tl_helpers import make_resolve_username_query

# Резолвить username
query = make_resolve_username_query("durov")
# Result: "pylogram.raw.functions.contacts.ResolveUsername(username='durov')"
```

**Что возвращает:**
- `peer` - информация о peer (Channel/User/Chat)
- `chats` - список чатов
- `users` - список пользователей

---

### 3. GetHistory - получить историю сообщений

```python
from telegram_tl_helpers import make_get_history_query, make_input_peer_channel

# Создаем InputPeer для канала
peer = make_input_peer_channel(channel_id=1234567, access_hash=9876543210)

# Получить последние 50 сообщений
query = make_get_history_query(
    peer=peer,
    limit=50
)
```

**Что возвращает:**
- `messages` - список сообщений
- `chats` - информация о чатах
- `users` - информация о пользователях

---

## 📝 Полный пример invoke запроса

```python
import httpx
from telegram_tl_helpers import make_get_dialogs_query

async def get_user_chats(session_id: str):
    # Создаем TL query
    query = make_get_dialogs_query(limit=20)
    
    # Формируем запрос
    payload = {
        "method": "invoke",
        "params": {
            "query": query,
            "retries": 10,
            "timeout": 15
        }
    }
    
    # Отправляем
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.knyazservice.com/api/external/sessions/{session_id}/rpc/invoke",
            json=payload
        )
        return response.json()
```

---

## 🎯 Пример ответа

```json
{
  "success": true,
  "error": null,
  "result": {
    "_": "types.messages.DialogsSlice",
    "count": 864,
    "dialogs": [
      {
        "_": "types.Dialog",
        "peer": {
          "_": "types.PeerChannel",
          "channel_id": 1259330770
        },
        "top_message": 33704722,
        "unread_count": 0,
        ...
      }
    ],
    "messages": [...],
    "chats": [
      {
        "_": "types.Channel",
        "id": 1259330770,
        "title": "Some Channel",
        "username": "somechannel",
        ...
      }
    ],
    "users": [...]
  },
  "session_deleted": false,
  "session_frozen": false
}
```

---

## ⚙️ Важные параметры

### retries
Количество повторов при временных ошибках (default: 10)

### timeout
Таймаут запроса в секундах (default: 15)

### sleep_threshold
Порог для sleep между retry (default: 10)

---

## 🔗 Полезные ссылки

- [Pylogram GitHub](https://github.com/pylakey/pylogram)
- [Telegram TL Schema (Layer 201)](https://github.com/pylakey/pylogram/blob/main/compiler/api/source/main_api.tl)
- [Telegram API Documentation](https://core.telegram.org/methods)

---

## ⚠️ Важно

**Версия pylogram должна совпадать** с версией на RPC сервере, чтобы Layer был одинаковый!

Текущая версия: **pylogram==0.12.3** (Layer 201)

