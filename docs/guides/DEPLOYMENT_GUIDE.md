# 🚀 Deployment Guide - Heat Up Service

Полное руководство по развертыванию Heat Up service на сервере.

---

## 📋 Что нужно предоставить агенту для развертывания

Если вы даете задачу агенту развернуть этот проект на сервере, передайте ему:

### 1. Обязательные данные:

```
Мне нужно развернуть Heat Up service на сервере.

Вот данные для .env файла:

DEEPSEEK_API_KEY=sk-xxxxx
TELEGRAM_API_BASE_URL=https://api.knyazservice.com
TELEGRAM_API_KEY=ваш_токен (опционально)

Порт: 8080 (или укажите другой)
Сервер: Ubuntu/Debian (или что используете)
```

### 2. Опциональные требования:

- Нужен ли systemd service для автозапуска?
- Нужен ли nginx reverse proxy?
- Нужен ли SSL/HTTPS?
- Какой домен использовать?

### 3. Файлы, которые агент должен проверить:

- ✅ `README.md` - основная документация
- ✅ `DEPLOYMENT_GUIDE.md` - этот файл
- ✅ `DOCKER_QUICK_START.md` - Docker инструкции
- ✅ `Dockerfile` - конфигурация Docker
- ✅ `docker-compose.yml` - Docker Compose настройка
- ✅ `requirements.txt` - зависимости Python
- ✅ `.dockerignore` - что исключить из образа
- ✅ `docs/guides/DEEPSEEK_MIGRATION.md` - информация о DeepSeek API

---

## 🐳 Развертывание через Docker (РЕКОМЕНДУЕТСЯ)

### Шаг 1: Подготовка сервера

```bash
# Обновить систему
sudo apt update && sudo apt upgrade -y

# Установить Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установить Docker Compose
sudo apt install docker-compose -y

# Добавить пользователя в группу docker (опционально)
sudo usermod -aG docker $USER
newgrp docker
```

### Шаг 2: Клонировать репозиторий

```bash
cd /opt  # или любая другая директория
git clone <repository_url> heat_up
cd heat_up
```

### Шаг 3: Настроить окружение

Создайте файл `.env`:

```bash
nano .env
```

**Содержимое .env:**

```env
# ===== ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ =====

# DeepSeek API (используется для всех LLM-агентов)
DEEPSEEK_API_KEY=sk-your-deepseek-key-here

# Telegram API Server
TELEGRAM_API_BASE_URL=https://api.knyazservice.com
TELEGRAM_API_KEY=optional-api-key-if-needed

# ===== ОПЦИОНАЛЬНЫЕ ПЕРЕМЕННЫЕ =====

# Логирование
LOG_LEVEL=INFO

# История сессий
SESSION_HISTORY_DAYS=30
DATABASE_PATH=sessions.db

# TGStat API (только если нужно обновлять каналы вручную)
TGSTAT_API_TOKEN=your-tgstat-token

# Scheduler (автоматический прогрев)
SCHEDULER_ENABLED=true
SCHEDULER_CHECK_INTERVAL=1800  # секунды (30 минут)
```

**Сохраните файл:** `Ctrl+O`, `Enter`, `Ctrl+X`

### Шаг 4: Обновить docker-compose.yml

Убедитесь, что `docker-compose.yml` использует `DEEPSEEK_API_KEY`:

```yaml
version: '3.8'

services:
  heat_up:
    build: .
    container_name: heat_up_service
    ports:
      - "8080:8080"
    env_file:
      - .env
    environment:
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - TELEGRAM_API_BASE_URL=${TELEGRAM_API_BASE_URL}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - TELEGRAM_API_KEY=${TELEGRAM_API_KEY:-}
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
      - ./sessions.db:/app/sessions.db  # Сохраняем БД на хосте
    networks:
      - heat_up_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  heat_up_network:
    driver: bridge
```

### Шаг 5: Запустить сервис

```bash
# Сборка и запуск
docker-compose up -d --build

# Проверить статус
docker-compose ps

# Смотреть логи
docker-compose logs -f

# Или только последние 100 строк
docker-compose logs --tail=100 -f
```

### Шаг 6: Проверка работоспособности

```bash
# Health check
curl http://localhost:8080/health

# Ожидаемый ответ:
# {"status":"healthy","timestamp":"..."}

# Проверить документацию API
curl http://localhost:8080/docs
```

### Шаг 7: Тестовый прогрев

```bash
# Замените 27084 на реальный session_id из вашей Telegram API
curl -X POST http://localhost:8080/warmup/27084
```

**Ожидаемый ответ:**

```json
{
  "session_id": "27084",
  "status": "started",
  "plan": {
    "actions": [
      {"action": "join_channel", "channel_username": "@example", ...},
      ...
    ]
  },
  "message": "Warmup plan created and execution started"
}
```

---

## 🔄 Автозапуск с systemd (альтернатива Docker)

Если не используете Docker:

### 1. Создать systemd service

```bash
sudo nano /etc/systemd/system/heat_up.service
```

**Содержимое:**

```ini
[Unit]
Description=Heat Up Telegram Warmup Service
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/opt/heat_up
Environment="PATH=/opt/heat_up/venv/bin"
ExecStart=/opt/heat_up/venv/bin/python /opt/heat_up/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Установить зависимости

```bash
cd /opt/heat_up
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Настроить .env (как в Docker)

### 4. Запустить service

```bash
sudo systemctl daemon-reload
sudo systemctl enable heat_up
sudo systemctl start heat_up

# Проверить статус
sudo systemctl status heat_up

# Смотреть логи
sudo journalctl -u heat_up -f
```

---

## 🌐 Nginx Reverse Proxy (опционально)

Если нужен доступ через домен с HTTPS:

### 1. Установить Nginx

```bash
sudo apt install nginx -y
```

### 2. Настроить конфигурацию

```bash
sudo nano /etc/nginx/sites-available/heat_up
```

**Содержимое:**

```nginx
server {
    listen 80;
    server_name heat-up.yourdomain.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (если понадобится в будущем)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3. Активировать и перезапустить

```bash
sudo ln -s /etc/nginx/sites-available/heat_up /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Установить SSL (Certbot)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d heat-up.yourdomain.com
```

---

## 📊 Мониторинг и обслуживание

### Логи

```bash
# Docker
docker-compose logs -f
docker-compose logs --tail=100 heat_up

# Systemd
sudo journalctl -u heat_up -f

# Файл логов (всегда)
tail -f logs/heat_up.log
```

### Проверка здоровья

```bash
# Health endpoint
curl http://localhost:8080/health

# Prometheus metrics (если настроены)
curl http://localhost:8080/metrics
```

### Обновление кода

```bash
cd /opt/heat_up
git pull

# Docker
docker-compose down
docker-compose up -d --build

# Systemd
sudo systemctl restart heat_up
```

### Очистка старых данных

```bash
# Очистить старые логи
find logs/ -name "*.log" -mtime +7 -delete

# Очистить старую историю сессий (выполняется автоматически)
# См. SESSION_HISTORY_DAYS в .env
```

---

## 🔍 Troubleshooting

### Проблема: Сервис не стартует

```bash
# Проверить логи
docker-compose logs
# или
sudo journalctl -u heat_up -n 100

# Частые причины:
# 1. Неправильный DEEPSEEK_API_KEY
# 2. Недоступен TELEGRAM_API_BASE_URL
# 3. Порт 8080 занят
```

### Проблема: "Connection refused" к Telegram API

```bash
# Проверить доступность API
curl -v https://api.knyazservice.com/health

# Проверить переменные окружения в контейнере
docker-compose exec heat_up env | grep TELEGRAM
```

### Проблема: DeepSeek API ошибки

```bash
# Проверить ключ
docker-compose exec heat_up python -c "from config import settings; print(settings.deepseek_api_key[:20])"

# Проверить квоту DeepSeek
curl https://api.deepseek.com/user/balance \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY"
```

### Проблема: Высокое потребление памяти

```bash
# Проверить статистику
docker stats heat_up_service

# Уменьшить частоту проверок scheduler
# В .env: SCHEDULER_CHECK_INTERVAL=3600  # 1 час
```

---

## 📦 Что входит в Docker образ

✅ **Включено:**
- Все Python модули (`*.py`)
- Зависимости (`requirements.txt`)
- Данные каналов (`data/channels_data.json`)
- Данные ботов (`data/bots_data.json`)
- OpenAPI спецификация (`data/openapi.json`)

❌ **Исключено (см. `.dockerignore`):**
- Документация (`docs/`, `*.md`)
- Скрипты разработки (`scripts/`)
- Тесты (`tests/`)
- Virtual environment (`venv/`)
- Git файлы (`.git/`)
- Временные файлы (`*.log`, `*.tmp`)

**Результат:** Легкий образ (~200-300MB) с только необходимым кодом.

---

## 🔐 Security Checklist

- [ ] `.env` файл **НЕ** в git (проверить `.gitignore`)
- [ ] DEEPSEEK_API_KEY не светится в логах
- [ ] TELEGRAM_API_KEY (если используется) безопасно хранится
- [ ] Nginx настроен с SSL (если публичный доступ)
- [ ] Firewall настроен (открыт только 80/443)
- [ ] Docker работает без root (пользователь в группе docker)
- [ ] Регулярные обновления системы (`apt update && apt upgrade`)

---

## 📞 Support

Если что-то не работает:

1. **Проверьте логи** (всегда первый шаг)
2. **Проверьте .env** (все ключи на месте?)
3. **Проверьте доступность API** (curl к Telegram и DeepSeek)
4. **Проверьте порты** (`netstat -tulpn | grep 8080`)
5. **Проверьте документацию** в `docs/guides/`

---

## 🎯 Quick Commands Reference

```bash
# === Docker ===
docker-compose up -d --build     # Запустить
docker-compose down              # Остановить
docker-compose logs -f           # Логи
docker-compose restart           # Перезапустить

# === Systemd ===
sudo systemctl start heat_up     # Запустить
sudo systemctl stop heat_up      # Остановить
sudo systemctl restart heat_up   # Перезапустить
sudo systemctl status heat_up    # Статус
sudo journalctl -u heat_up -f    # Логи

# === API ===
curl http://localhost:8080/health                    # Здоровье
curl -X POST http://localhost:8080/warmup/SESSION_ID # Прогрев
curl http://localhost:8080/docs                       # Swagger UI
curl http://localhost:8080/sessions/SESSION_ID/history # История

# === Мониторинг ===
docker stats heat_up_service     # Статистика контейнера
tail -f logs/heat_up.log          # Логи приложения
du -sh logs/                      # Размер логов
```

---

✅ **С этим гайдом любой агент сможет развернуть проект на сервере!**

