# 📋 Гайд по логам системы

## 🚀 Быстрый старт

### **Интерактивный мониторинг (рекомендуется)**
```bash
./watch_logs.sh
```

---

## 📊 Прямые команды

### **1. Основной лог приложения (все действия)**
```bash
tail -f logs/heat_up.log
```

### **2. Лог веб-сервера (HTTP запросы)**
```bash
tail -f server.log
```

### **3. Оба лога одновременно**
```bash
tail -f logs/heat_up.log server.log
```

### **4. Только последние 50 строк**
```bash
tail -50 logs/heat_up.log
```

---

## 🔍 Фильтрация логов

### **Только ошибки (ERROR)**
```bash
tail -f logs/heat_up.log | grep --line-buffered "ERROR"
```

### **Только предупреждения (WARNING)**
```bash
tail -f logs/heat_up.log | grep --line-buffered "WARNING"
```

### **Только scheduler (автопрогрев)**
```bash
tail -f logs/heat_up.log | grep --line-buffered "scheduler"
```

### **Только executor (выполнение действий)**
```bash
tail -f logs/heat_up.log | grep --line-buffered "executor"
```

### **Только persona_agent (генерация личностей)**
```bash
tail -f logs/heat_up.log | grep --line-buffered "persona_agent"
```

### **Только LLM запросы**
```bash
tail -f logs/heat_up.log | grep --line-buffered "llm_agent"
```

### **Только telegram_client (действия в Telegram)**
```bash
tail -f logs/heat_up.log | grep --line-buffered "telegram_client"
```

---

## 🎯 Полезные комбинации

### **Мониторинг прогрева в реальном времени**
```bash
tail -f logs/heat_up.log | grep --line-buffered -E "scheduler|executor|EXECUTING ACTION"
```

### **Только успешные действия**
```bash
tail -f logs/heat_up.log | grep --line-buffered "✅"
```

### **Только ошибки и предупреждения**
```bash
tail -f logs/heat_up.log | grep --line-buffered -E "ERROR|WARNING"
```

### **Активность конкретной сессии**
```bash
tail -f logs/heat_up.log | grep --line-buffered "test_002"
```

---

## 📈 Статистика по логам

### **Подсчет ошибок**
```bash
grep "ERROR" logs/heat_up.log | wc -l
```

### **Последние 10 ошибок**
```bash
grep "ERROR" logs/heat_up.log | tail -10
```

### **Сколько раз прогревался каждый аккаунт**
```bash
grep "Starting warmup for account" logs/heat_up.log | cut -d' ' -f10 | sort | uniq -c
```

### **Сколько действий выполнено**
```bash
grep "EXECUTING ACTION" logs/heat_up.log | wc -l
```

---

## 🧹 Очистка логов

### **Очистить старые логи**
```bash
> logs/heat_up.log
> server.log
echo "✅ Логи очищены"
```

### **Архивировать и очистить**
```bash
tar -czf logs_backup_$(date +%Y%m%d_%H%M%S).tar.gz logs/heat_up.log server.log
> logs/heat_up.log
> server.log
echo "✅ Логи заархивированы и очищены"
```

---

## 🎨 Цветной вывод (опционально)

### **Установка ccze (colorizer)**
```bash
# macOS
brew install ccze

# Использование
tail -f logs/heat_up.log | ccze -A
```

### **Или используй grep с цветом**
```bash
tail -f logs/heat_up.log | grep --color=always -E "ERROR|WARNING|INFO|$"
```

---

## 💡 Полезные советы

1. **Ctrl+C** - остановить tail -f
2. **Ctrl+Z** затем `bg` - отправить процесс в фон
3. Используй `tmux` или `screen` для постоянного мониторинга
4. **Shift+PgUp/PgDn** - прокрутка в терминале (если поддерживается)

---

## 🔧 Если логов слишком много

Настрой rotation в `config.py`:
```python
log_max_bytes = 10485760  # 10MB
log_backup_count = 5       # Держать 5 старых файлов
```

---

**Нажми Ctrl+C чтобы выйти из режима мониторинга!**

