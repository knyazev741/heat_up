# 🐳 Docker Quick Start

## Запуск в Docker

После реструктуризации проект полностью готов к запуску в Docker.

### 1. Подготовка

```bash
# Убедитесь что .env настроен
cp .env.example .env
nano .env  # Добавьте ваши API ключи
```

### 2. Сборка и запуск

```bash
# Сборка образа
docker-compose build

# Запуск
docker-compose up -d

# Или одной командой
docker-compose up -d --build
```

### 3. Проверка

```bash
# Проверить статус
docker-compose ps

# Смотреть логи
docker-compose logs -f

# Проверить здоровье
curl http://localhost:8080/health
```

## Что включено в образ

✅ Все Python модули из корня  
✅ Данные из `data/` (channels, bots, openapi)  
✅ Конфигурация из `.env`  
❌ Документация (исключена через .dockerignore)  
❌ Скрипты разработки (исключены)  
❌ Тесты (исключены)  

## Оптимизация

Благодаря `.dockerignore` Docker образ **не включает**:
- Документацию (docs/)
- Скрипты разработки (scripts/)
- Тесты (tests/)
- Virtual environment (venv/)
- Git файлы

**Результат:** Меньший размер образа и быстрая сборка.

## Volumes

```yaml
volumes:
  - ./logs:/app/logs  # Логи сохраняются на хосте
```

Логи доступны в `./logs/heat_up.log`

## Остановка

```bash
# Остановить
docker-compose stop

# Остановить и удалить
docker-compose down

# Удалить с volumes
docker-compose down -v
```

## Обновление

```bash
# При изменении кода
docker-compose down
docker-compose up -d --build

# Пересоздать базу данных
docker-compose down -v
docker-compose up -d
```

---

✅ **Проект готов к запуску в Docker!**

