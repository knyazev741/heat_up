# Session Filtering Implementation - Changelog

**Дата**: 3 ноября 2025  
**Задача**: Реализовать проверку сессий перед генерацией LLM планов для экономии токенов

---

## 🎯 Цель

Исключить из прогрева сессии, которые:
- Заморожены (`is_frozen`)
- Удалены (`is_deleted`)
- Забанены навсегда (`is_banned` без `unban_date`)
- Имеют отключенную генерацию LLM вручную (`llm_generation_disabled`)

---

## 📝 Изменения

### 1. База данных (`database.py`)

#### Новые поля в таблице `accounts`:
```sql
is_deleted BOOLEAN DEFAULT 0
unban_date DATETIME
llm_generation_disabled BOOLEAN DEFAULT 0
```

#### Автоматическая миграция:
- Добавлены проверки существования новых столбцов
- При отсутствии автоматически выполняется `ALTER TABLE ADD COLUMN`
- Полная обратная совместимость с существующими БД

#### Новые функции:

**`should_skip_warmup(account: Dict) -> tuple[bool, str]`**
- Проверяет сессию по всем критериям исключения
- Возвращает `(should_skip, reason)`
- 6 проверок в приоритетном порядке

**Обновлена `get_accounts_for_warmup()`**
- SQL-фильтрация исключенных сессий на уровне запроса
- Автоматическая разблокировка при истечении `unban_date`

### 2. Планировщик (`scheduler.py`)

**Проверка в `warmup_account()`** (строка ~216):
```python
should_skip, skip_reason = should_skip_warmup(account)
if should_skip:
    logger.warning(f"⚠️ SKIPPING warmup: {skip_reason}")
    return
```

**Импорт**:
```python
from database import should_skip_warmup
```

### 3. API эндпоинты (`main.py`)

**Проверка в `/warmup/{session_id}`** (строка ~193):
**Проверка в `/warmup-sync/{session_id}`** (строка ~279):

```python
from database import should_skip_warmup

if account_data:
    should_skip, skip_reason = should_skip_warmup(account_data)
    if should_skip:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot warmup session: {skip_reason}"
        )
```

### 4. Модели данных (`models.py`)

**`UpdateAccountRequest`** - добавлены поля:
- `is_deleted: Optional[bool]`
- `unban_date: Optional[str]`
- `llm_generation_disabled: Optional[bool]`

**`AccountResponse`** - добавлены поля:
- `is_deleted: bool = False`
- `unban_date: Optional[str] = None`
- `llm_generation_disabled: bool = False`

---

## 📚 Документация

### Создано:
- `docs/guides/SESSION_FILTERING_GUIDE.md` - полное руководство
  - Описание логики работы
  - Примеры использования API
  - SQL-запросы для администрирования
  - Мониторинг

### Тесты:
- `scripts/test_session_filtering.py` - автоматические тесты
  - 8 тестовых сценариев для `should_skip_warmup()`
  - Проверка `get_accounts_for_warmup()`

---

## 🔍 Логика проверок

### Порядок проверок (приоритет):

1. ❌ `is_deleted = 1` → "session is deleted"
2. ❌ `is_frozen = 1` → "session is frozen"  
3. ❌ `is_banned = 1 AND unban_date IS NULL` → "session is banned forever"
4. ⏳ `is_banned = 1 AND unban_date > NOW()` → "session is temporarily banned until {date}"
5. 🚫 `llm_generation_disabled = 1` → "LLM generation is manually disabled"
6. 💤 `is_active = 0` → "session is not active"

### SQL-фильтр в `get_accounts_for_warmup()`:

```sql
WHERE is_active = 1 
  AND is_deleted = 0 
  AND is_frozen = 0 
  AND llm_generation_disabled = 0
  AND (is_banned = 0 OR (is_banned = 1 AND unban_date IS NOT NULL AND unban_date <= datetime('now')))
```

---

## 🧪 Тестирование

### Запуск тестов:
```bash
cd /root/heat_up
python scripts/test_session_filtering.py
```

### Ожидаемый вывод:
```
🧪 Testing should_skip_warmup() function
1. Normal active session
   ✅ PASSED
...
📊 Test Results: 8 passed, 0 failed out of 8 total

🧪 Testing get_accounts_for_warmup() function
✅ All returned accounts are valid for warmup

🏁 FINAL RESULTS
✅ PASSED: should_skip_warmup()
✅ PASSED: get_accounts_for_warmup()
🎉 All tests PASSED!
```

---

## 📊 Примеры использования

### Отключить генерацию LLM для сессии:
```bash
curl -X PATCH http://localhost:8000/accounts/27084 \
  -H "Content-Type: application/json" \
  -d '{"llm_generation_disabled": true}'
```

### Установить бан навсегда:
```bash
curl -X PATCH http://localhost:8000/accounts/27084 \
  -H "Content-Type: application/json" \
  -d '{"is_banned": true, "unban_date": null}'
```

### Установить временный бан:
```bash
curl -X PATCH http://localhost:8000/accounts/27084 \
  -H "Content-Type: application/json" \
  -d '{"is_banned": true, "unban_date": "2025-11-10T12:00:00"}'
```

---

## ✅ Преимущества

1. **💰 Экономия токенов LLM** - не генерируем планы для неактивных сессий
2. **🎯 Гибкое управление** - несколько типов блокировок
3. **⏰ Временные баны** - автоматическая разблокировка
4. **🔧 Ручное управление** - флаг `llm_generation_disabled`
5. **↩️ Обратная совместимость** - автоматическая миграция БД
6. **📊 SQL-фильтрация** - эффективная выборка на уровне БД

---

## 🚀 Deployment

### Миграция существующей БД:
Происходит автоматически при первом запуске после обновления:
```python
# database.py:init_database()
# Автоматически добавляет новые столбцы если их нет
```

### Новые установки:
Все поля создаются автоматически при инициализации БД.

---

## 📈 Мониторинг

### Проверка исключенных сессий:
```bash
sqlite3 data/sessions.db "
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN is_deleted = 1 THEN 1 ELSE 0 END) as deleted,
  SUM(CASE WHEN is_frozen = 1 THEN 1 ELSE 0 END) as frozen,
  SUM(CASE WHEN is_banned = 1 AND unban_date IS NULL THEN 1 ELSE 0 END) as banned_forever,
  SUM(CASE WHEN llm_generation_disabled = 1 THEN 1 ELSE 0 END) as llm_disabled
FROM accounts;
"
```

---

## 📝 Файлы изменены

1. ✅ `database.py` - схема БД, проверки, миграция
2. ✅ `scheduler.py` - проверка перед генерацией плана
3. ✅ `main.py` - проверка в API эндпоинтах
4. ✅ `models.py` - новые поля в моделях

## 📝 Файлы созданы

1. ✅ `docs/guides/SESSION_FILTERING_GUIDE.md`
2. ✅ `scripts/test_session_filtering.py`
3. ✅ `SESSION_FILTERING_CHANGELOG.md` (этот файл)

---

## ✨ Статус

**✅ ЗАВЕРШЕНО** - Все задачи выполнены, код протестирован, документация создана.

