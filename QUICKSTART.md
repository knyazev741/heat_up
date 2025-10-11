# 🚀 Quick Start Guide

Быстрый старт за 5 минут!

## Шаг 1: Настройка (2 мин)

```bash
cd /Users/knyaz/heat_up

# Создать .env файл
cp .env.example .env

# Отредактировать .env и добавить:
# OPENAI_API_KEY=sk-proj-ваш-реальный-ключ
# TELEGRAM_API_BASE_URL=http://ваш-telegram-api:8000
nano .env  # или любой другой редактор
```

## Шаг 2: Валидация (30 сек)

```bash
python3 validate_setup.py
```

Должны увидеть:
```
✅ All checks passed! Ready to start.
```

Если есть ошибки - следуйте инструкциям в выводе.

## Шаг 3: Запуск (1 мин)

### Вариант A: Автоматический (рекомендуется)
```bash
./start.sh
```

### Вариант B: Ручной
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Вариант C: Docker
```bash
docker-compose up -d
docker-compose logs -f
```

## Шаг 4: Тест (1 мин)

### A. Проверка работоспособности
```bash
curl http://localhost:8080/health
```

Ответ:
```json
{
  "status": "healthy",
  "telegram_client": true,
  "llm_agent": true
}
```

### B. Тестовый прогрев (async)
```bash
curl -X POST http://localhost:8080/warmup/test_session_12345
```

Ответ:
```json
{
  "session_id": "test_session_12345",
  "status": "started",
  "message": "Warmup initiated with 5 actions",
  "action_plan": [...]
}
```

### C. Полный прогрев с отчетом (sync)
```bash
curl -X POST http://localhost:8080/warmup-sync/test_session_12345
```

### D. Через Python
```bash
python example_usage.py
```

## Шаг 5: Продакшн использование

### Простейший вариант:
```python
import httpx

async def warmup_new_account(session_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8080/warmup/{session_id}"
        )
        return response.json()
```

### С обработкой ошибок:
```python
import httpx
import logging

logger = logging.getLogger(__name__)

async def warmup_account_safe(session_id: str) -> dict:
    """Безопасный прогрев с error handling"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"http://localhost:8080/warmup/{session_id}"
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(
                f"Warmup started for {session_id}: "
                f"{len(result['action_plan'])} actions"
            )
            
            return result
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code}")
        return {"error": str(e), "session_id": session_id}
    except Exception as e:
        logger.error(f"Warmup failed: {str(e)}")
        return {"error": str(e), "session_id": session_id}
```

## 📚 Далее

- **Документация**: см. `README.md`
- **API Docs**: http://localhost:8080/docs
- **Примеры**: см. `example_usage.py`
- **Детали проекта**: см. `PROJECT_SUMMARY.md`

## ❓ Troubleshooting

### Проблема: "Missing packages"
```bash
pip install -r requirements.txt
```

### Проблема: ".env file contains placeholder values"
Отредактируйте `.env` и замените `sk-proj-xxx` на реальный ключ OpenAI

### Проблема: "Service unavailable"
Проверьте:
1. Сервис запущен: `ps aux | grep main.py`
2. Порт свободен: `lsof -i :8080`
3. Логи: смотрите вывод `python main.py`

### Проблема: "OpenAI API error"
- Проверьте баланс API ключа
- Проверьте интернет-соединение
- Проверьте правильность ключа в `.env`

### Проблема: "Telegram API error"
- Проверьте `TELEGRAM_API_BASE_URL` в `.env`
- Убедитесь что Telegram API сервис работает
- Проверьте что session_id существует

## 🎯 Типичные сценарии

### Сценарий 1: Прогрев одной сессии
```bash
curl -X POST http://localhost:8080/warmup/abc123
```

### Сценарий 2: Batch прогрев нескольких сессий
```python
import asyncio
import httpx

async def warmup_batch(session_ids: list):
    async with httpx.AsyncClient() as client:
        tasks = [
            client.post(f"http://localhost:8080/warmup/{sid}")
            for sid in session_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

session_ids = ["session1", "session2", "session3"]
results = asyncio.run(warmup_batch(session_ids))
```

### Сценарий 3: Прогрев с кастомным API
```bash
curl -X POST http://localhost:8080/warmup/abc123 \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_api_base_url": "http://custom-api:9000",
    "telegram_api_key": "custom-key"
  }'
```

## ✅ Checklist готовности к продакшну

- [ ] `.env` файл настроен с реальными ключами
- [ ] `validate_setup.py` проходит успешно
- [ ] Тестовый запрос возвращает корректный результат
- [ ] Логи пишутся корректно
- [ ] Настроен мониторинг (health checks)
- [ ] Настроен reverse proxy (если нужен)
- [ ] Рассмотрена настройка rate limiting
- [ ] Документирован процесс деплоя

---

Вопросы? См. README.md или PROJECT_SUMMARY.md

