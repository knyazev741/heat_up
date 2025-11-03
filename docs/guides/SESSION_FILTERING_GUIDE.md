# Руководство по фильтрации сессий прогрева

## Обзор

Реализована система фильтрации сессий перед генерацией шагов прогрева для экономии токенов LLM.

## Новые поля в таблице `accounts`

### 1. `is_deleted` (BOOLEAN)
- **Значение по умолчанию**: `0` (false)
- **Назначение**: Флаг удаленных сессий
- **Поведение**: Сессии с `is_deleted = 1` полностью исключаются из прогрева

### 2. `unban_date` (DATETIME)
- **Значение по умолчанию**: `NULL`
- **Назначение**: Дата разбана (если установлена)
- **Поведение**: 
  - Если `is_banned = 1` и `unban_date IS NULL` → **бан навсегда** (forever banned)
  - Если `is_banned = 1` и `unban_date` в будущем → **временный бан**
  - Если `is_banned = 1` и `unban_date` в прошлом → сессия автоматически разбанивается

### 3. `llm_generation_disabled` (BOOLEAN)
- **Значение по умолчанию**: `0` (false)
- **Назначение**: Ручное отключение генерации LLM для экономии токенов
- **Поведение**: Сессии с `llm_generation_disabled = 1` не будут генерировать планы действий

## Логика проверки сессий

Функция `should_skip_warmup()` проверяет сессию по следующим критериям:

```python
# database.py
def should_skip_warmup(account: Dict[str, Any]) -> tuple[bool, str]:
    """
    Проверить, нужно ли пропустить прогрев сессии
    
    Returns:
        (should_skip: bool, reason: str)
    """
```

### Порядок проверок:

1. ❌ **is_deleted** → `"session is deleted"`
2. ❌ **is_frozen** → `"session is frozen"`
3. ❌ **is_banned + no unban_date** → `"session is banned forever"`
4. ⏳ **is_banned + unban_date (future)** → `"session is temporarily banned until {date}"`
5. 🚫 **llm_generation_disabled** → `"LLM generation is manually disabled"`
6. 💤 **not is_active** → `"session is not active"`

## Места интеграции проверок

### 1. Планировщик (`scheduler.py`)

Проверка происходит **перед генерацией плана действий**:

```python
# scheduler.py:warmup_account()
should_skip, skip_reason = should_skip_warmup(account)
if should_skip:
    logger.warning(f"⚠️ SKIPPING warmup for session {session_id}: {skip_reason}")
    logger.warning(f"   This session will be excluded from warmup to save LLM tokens")
    return
```

### 2. API эндпоинты (`main.py`)

Проверка в обоих эндпоинтах:
- `/warmup/{session_id}` (async)
- `/warmup-sync/{session_id}` (sync)

```python
if account_data:
    should_skip, skip_reason = should_skip_warmup(account_data)
    if should_skip:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot warmup session: {skip_reason}. This session is excluded to save LLM tokens."
        )
```

### 3. Получение аккаунтов (`get_accounts_for_warmup()`)

SQL-запрос автоматически фильтрует:

```sql
SELECT * FROM accounts 
WHERE is_active = 1 
  AND is_deleted = 0 
  AND is_frozen = 0 
  AND llm_generation_disabled = 0
  AND (is_banned = 0 OR (is_banned = 1 AND unban_date IS NOT NULL AND unban_date <= datetime('now')))
ORDER BY last_warmup_date ASC NULLS FIRST
```

## Примеры использования

### Пример 1: Пометить сессию как удаленную

```bash
curl -X PATCH http://localhost:8000/accounts/27084 \
  -H "Content-Type: application/json" \
  -d '{
    "is_deleted": true
  }'
```

### Пример 2: Установить временный бан

```bash
curl -X PATCH http://localhost:8000/accounts/27084 \
  -H "Content-Type: application/json" \
  -d '{
    "is_banned": true,
    "unban_date": "2025-11-10T12:00:00"
  }'
```

### Пример 3: Установить бан навсегда

```bash
curl -X PATCH http://localhost:8000/accounts/27084 \
  -H "Content-Type: application/json" \
  -d '{
    "is_banned": true,
    "unban_date": null
  }'
```

### Пример 4: Отключить генерацию LLM вручную

```bash
curl -X PATCH http://localhost:8000/accounts/27084 \
  -H "Content-Type: application/json" \
  -d '{
    "llm_generation_disabled": true
  }'
```

### Пример 5: Разбанить сессию

```bash
curl -X PATCH http://localhost:8000/accounts/27084 \
  -H "Content-Type: application/json" \
  -d '{
    "is_banned": false,
    "unban_date": null
  }'
```

## SQL-запросы для администрирования

### Найти все забаненные навсегда сессии

```sql
SELECT session_id, phone_number, ban_date
FROM accounts
WHERE is_banned = 1 AND unban_date IS NULL;
```

### Найти все временно забаненные сессии

```sql
SELECT session_id, phone_number, unban_date
FROM accounts
WHERE is_banned = 1 AND unban_date IS NOT NULL;
```

### Найти все сессии с отключенной генерацией LLM

```sql
SELECT session_id, phone_number, llm_generation_disabled
FROM accounts
WHERE llm_generation_disabled = 1;
```

### Найти все замороженные сессии

```sql
SELECT session_id, phone_number, frozen_date
FROM accounts
WHERE is_frozen = 1;
```

### Массовое отключение LLM для определенных сессий

```sql
UPDATE accounts 
SET llm_generation_disabled = 1
WHERE session_id IN ('27082', '27083', '27084');
```

## Логи

### Успешный пропуск сессии (scheduler)

```
⚠️ SKIPPING warmup for session 27084: session is frozen
   This session will be excluded from warmup to save LLM tokens
```

### Отклонение через API

```
⚠️ REJECTING warmup request for session 27084: session is banned forever (no unban_date)
HTTP 400: Cannot warmup session: session is banned forever (no unban_date). This session is excluded to save LLM tokens.
```

## Миграция существующих баз данных

При первом запуске после обновления автоматически добавляются новые столбцы:

```python
# database.py:init_database()
# Migrate existing tables - add new columns if they don't exist
try:
    cursor.execute("SELECT is_deleted FROM accounts LIMIT 1")
except sqlite3.OperationalError:
    cursor.execute("ALTER TABLE accounts ADD COLUMN is_deleted BOOLEAN DEFAULT 0")

try:
    cursor.execute("SELECT unban_date FROM accounts LIMIT 1")
except sqlite3.OperationalError:
    cursor.execute("ALTER TABLE accounts ADD COLUMN unban_date DATETIME")

try:
    cursor.execute("SELECT llm_generation_disabled FROM accounts LIMIT 1")
except sqlite3.OperationalError:
    cursor.execute("ALTER TABLE accounts ADD COLUMN llm_generation_disabled BOOLEAN DEFAULT 0")
```

## Преимущества

✅ **Экономия токенов LLM** - не генерируем планы для неактивных сессий
✅ **Гибкое управление** - разные типы блокировок
✅ **Временные баны** - автоматическая разблокировка после unban_date
✅ **Ручное управление** - флаг llm_generation_disabled
✅ **Обратная совместимость** - автоматическая миграция существующих баз

## Мониторинг

Рекомендуется периодически проверять:

```bash
# Количество исключенных сессий
sqlite3 data/sessions.db "
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN is_deleted = 1 THEN 1 ELSE 0 END) as deleted,
  SUM(CASE WHEN is_frozen = 1 THEN 1 ELSE 0 END) as frozen,
  SUM(CASE WHEN is_banned = 1 AND unban_date IS NULL THEN 1 ELSE 0 END) as banned_forever,
  SUM(CASE WHEN llm_generation_disabled = 1 THEN 1 ELSE 0 END) as llm_disabled
FROM accounts
WHERE is_active = 1;
"
```

