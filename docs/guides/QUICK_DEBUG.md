# 🔍 Быстрая шпаргалка по отладке

## Запуск с логированием

```bash
# Запуск в фоне
./venv/bin/python main.py &

# Запуск с выводом в консоль
./venv/bin/python main.py

# Остановка
pkill -f "python main.py"
```

## Просмотр логов (используй скрипт!)

```bash
./view_logs.sh              # Последние 50 строк
./view_logs.sh live         # Следить в реальном времени
./view_logs.sh llm          # Только промпты + ответы LLM
./view_logs.sh actions      # Только действия
./view_logs.sh errors       # Только ошибки
```

## Типичные сценарии отладки

### 1. Проверить что отправляется в LLM

```bash
./view_logs.sh llm | grep -A 100 "SYSTEM PROMPT"
```

Увидишь:
- Весь промпт со списком каналов/ботов
- Инструкции для LLM
- User context (новый/returning пользователь)

### 2. Посмотреть ответ LLM

```bash
./view_logs.sh llm | grep -A 50 "RAW RESPONSE"
```

Увидишь JSON с действиями, которые сгенерировала модель.

### 3. Проверить выполнение конкретного действия

```bash
# Смотри все действия
./view_logs.sh actions

# Или в файле найди нужное
grep "EXECUTING ACTION" logs/heat_up.log
```

### 4. Найти почему что-то упало

```bash
./view_logs.sh errors
```

### 5. Следить за выполнением в реальном времени

```bash
# Терминал 1: запусти сервис
./venv/bin/python main.py

# Терминал 2: запусти warmup
curl -X POST http://localhost:8080/warmup/test_session

# Терминал 3: следи за логами
./view_logs.sh live
```

## Что искать в логах

### ✅ Нормальное поведение

```
📤 SENDING TO LLM (GPT-4o-mini)
📥 RECEIVED FROM LLM
✅ VALIDATION COMPLETE: 12 / 12 actions passed
🎬 EXECUTING ACTION #1/12: VIEW_PROFILE
✅ ACTION SUCCEEDED: view_profile
```

### ❌ Проблемы

```
❌ JSON PARSE ERROR: ...           # LLM вернул невалидный JSON
❌ ACTION FAILED: ...               # Действие упало
ERROR - Failed to ...               # Любая ошибка
```

## Файлы логов

- `logs/heat_up.log` - основной файл с ВСЕМИ логами
- `console_output.log` - если запускал с `tee`

## Очистка

```bash
./view_logs.sh clear    # Очистить лог файл

# Или архивировать
mv logs/heat_up.log logs/backup_$(date +%Y%m%d).log
```

## Live мониторинг (best practice)

Открой 2 терминала:

**Терминал 1** (сервис):
```bash
cd /Users/knyaz/heat_up
./venv/bin/python main.py
```

**Терминал 2** (тесты + мониторинг):
```bash
cd /Users/knyaz/heat_up

# Запусти warmup
curl -X POST http://localhost:8080/warmup/my_test_session

# Или следи за логами
./view_logs.sh live
```

## Grep паттерны (для продвинутых)

```bash
# Все промпты к LLM за сегодня
grep "SYSTEM PROMPT" logs/heat_up.log

# Все ошибки с контекстом (5 строк до/после)
grep -C 5 "ERROR" logs/heat_up.log

# Только успешные действия
grep "ACTION SUCCEEDED" logs/heat_up.log

# Действия конкретного типа
grep "react_to_message" logs/heat_up.log

# Статистика по действиям
grep "EXECUTING ACTION" logs/heat_up.log | wc -l

# Успешность
grep -c "ACTION SUCCEEDED" logs/heat_up.log
grep -c "ACTION FAILED" logs/heat_up.log
```

Happy debugging! 🐛🔨

