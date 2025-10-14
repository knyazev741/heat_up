# Шпаргалка - Прогрев аккаунтов

## 🚀 Быстрый старт (3 команды)

```bash
# 1. Запустить сервис
python main.py

# 2. Добавить аккаунты (в другом терминале)
./add_accounts_interactive.sh

# 3. Смотреть что происходит
./monitor.sh
```

## 📊 Мониторинг

| Команда | Что показывает |
|---------|----------------|
| `./monitor.sh` | Полный дашборд со всеми метриками |
| `tail -f logs/heat_up.log` | Логи в реальном времени |
| `curl http://localhost:8080/statistics \| jq` | Общая статистика |
| `curl http://localhost:8080/accounts \| jq` | Список всех аккаунтов |

## 🔧 Управление аккаунтами

```bash
# Добавить аккаунт
curl -X POST http://localhost:8080/accounts/add \
  -H "Content-Type: application/json" \
  -d '{"session_id":"ses1","phone_number":"+79991234567","daily_activity_count":3}'

# Список аккаунтов
curl http://localhost:8080/accounts | jq

# Детали аккаунта (замени 1 на нужный ID)
curl http://localhost:8080/accounts/1 | jq

# Проверить здоровье
curl http://localhost:8080/accounts/1/health | jq

# Запустить прогрев сейчас
curl -X POST http://localhost:8080/accounts/1/warmup-now

# Изменить частоту прогрева
curl -X POST http://localhost:8080/accounts/1/update \
  -H "Content-Type: application/json" \
  -d '{"daily_activity_count":4}'

# Деактивировать
curl -X POST http://localhost:8080/accounts/1/update \
  -H "Content-Type: application/json" \
  -d '{"is_active":false}'
```

## 🤖 Управление scheduler

```bash
# Статус
curl http://localhost:8080/scheduler/status | jq

# Остановить
curl -X POST http://localhost:8080/scheduler/stop

# Запустить
curl -X POST http://localhost:8080/scheduler/start
```

## 📈 Статистика

```bash
# Общая статистика
curl http://localhost:8080/statistics | jq

# Отчет за сегодня
curl http://localhost:8080/statistics/daily | jq

# Здоровье конкретного аккаунта
curl http://localhost:8080/accounts/1/health | jq
```

## 🔍 Поиск в логах

```bash
# Последние 50 строк
tail -50 logs/heat_up.log

# Только ошибки
grep ERROR logs/heat_up.log | tail -20

# FloodWait события
grep -i flood logs/heat_up.log

# Прогревы конкретного аккаунта
grep "account.*1" logs/heat_up.log | tail -30

# Успешные действия
grep "✅" logs/heat_up.log | tail -20
```

## 🛠 Решение проблем

### Аккаунт заморожен (FloodWait)

```bash
# 1. Проверить
curl http://localhost:8080/accounts/1/health | jq

# 2. Подождать 24-48 часов

# 3. Снять флаг
curl -X POST http://localhost:8080/accounts/1/update \
  -H "Content-Type: application/json" \
  -d '{"is_frozen":false}'

# 4. Снизить активность
curl -X POST http://localhost:8080/accounts/1/update \
  -H "Content-Type: application/json" \
  -d '{"daily_activity_count":2}'
```

### Сервис не отвечает

```bash
# Проверить процесс
ps aux | grep "python main.py"

# Проверить порт
lsof -i :8080

# Перезапустить
pkill -f "python main.py"
python main.py
```

### Scheduler не работает

```bash
# Проверить статус
curl http://localhost:8080/scheduler/status

# Перезапустить
curl -X POST http://localhost:8080/scheduler/stop
sleep 2
curl -X POST http://localhost:8080/scheduler/start
```

## 📁 Структура файлов

```
/Users/knyaz/heat_up/
├── main.py                          # Сервис (запускать)
├── logs/heat_up.log                 # Основной лог
├── sessions.db                      # База данных
├── monitor.sh                       # Мониторинг
├── add_accounts_interactive.sh      # Добавление аккаунтов
├── QUICKSTART_ПРОГРЕВ.md           # Полная инструкция
└── CHEATSHEET.md                    # Эта шпаргалка
```

## 🎯 Типичные сценарии

### Добавить 3 аккаунта и запустить прогрев

```bash
# Терминал 1: Запустить сервис
python main.py

# Терминал 2: Добавить аккаунты
./add_accounts_interactive.sh
# Ввести данные для 3 аккаунтов

# Терминал 3: Мониторинг
watch -n 10 './monitor.sh'
```

### Проверить состояние системы

```bash
./monitor.sh
```

### Посмотреть что делает конкретный аккаунт

```bash
# Детали
curl http://localhost:8080/accounts/1 | jq

# Последняя сессия прогрева
curl http://localhost:8080/accounts/1 | jq '.recent_warmup_sessions[0]'

# Найденные чаты
curl http://localhost:8080/accounts/1 | jq '.discovered_chats'

# Личность
curl http://localhost:8080/accounts/1 | jq '.persona'
```

## 📞 Полезные алиасы (добавь в ~/.zshrc)

```bash
alias warmup-status='curl -s http://localhost:8080/statistics | jq'
alias warmup-accounts='curl -s http://localhost:8080/accounts | jq'
alias warmup-logs='tail -f /Users/knyaz/heat_up/logs/heat_up.log'
alias warmup-monitor='cd /Users/knyaz/heat_up && ./monitor.sh'
```

## 🎓 Понимание стадий прогрева

| Стадия | Что происходит | Действий |
|--------|----------------|----------|
| 1 | Настройка профиля | 2-3 |
| 2-3 | Вступление в 1-2 канала | 3-7 |
| 4-7 | Чтение, реакции, боты | 5-12 |
| 8-14 | Активное участие, группы | 10-15 |
| 15+ | Готов к работе | Полная активность |

## ⏰ Частота прогрева

| daily_activity_count | Интервал между прогревами |
|----------------------|---------------------------|
| 2 | ~12 часов |
| 3 | ~8 часов |
| 4 | ~6 часов |
| 5 | ~5 часов |

**Рекомендуется: 3** (оптимальный баланс)

## 🔔 Важно помнить

- ✅ Система работает автоматически - scheduler сам запускает прогрев
- ✅ Каждый аккаунт получает уникальную личность
- ✅ Прогрев постепенный - 14 дней до полной активности
- ✅ Все логируется в `logs/heat_up.log`
- ⚠️ При FloodWait - подождать 24-48 часов
- ⚠️ Не запускать прогрев пока аккаунт используется для рассылок

## 🆘 Срочная помощь

```bash
# Все аккаунты сломались?
curl http://localhost:8080/statistics/daily | jq

# Что с конкретным аккаунтом?
curl http://localhost:8080/accounts/1/health | jq

# Последние ошибки?
grep ERROR logs/heat_up.log | tail -10

# Перезапустить все?
pkill -f "python main.py"
sleep 2
python main.py
```

