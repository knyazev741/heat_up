#!/bin/bash
# Скрипт для мониторинга логов в реальном времени

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 МОНИТОРИНГ ЛОГОВ HEAT_UP SYSTEM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Выбери что смотреть:"
echo "  1) Основной лог приложения (logs/heat_up.log)"
echo "  2) Лог сервера uvicorn (server.log)"
echo "  3) Оба лога одновременно (split view)"
echo "  4) Только ERRORS"
echo "  5) Только INFO от scheduler"
echo ""
read -p "Выбор [1-5]: " choice

case $choice in
    1)
        echo "📋 Следим за logs/heat_up.log (Ctrl+C для выхода)..."
        tail -f logs/heat_up.log
        ;;
    2)
        echo "📋 Следим за server.log (Ctrl+C для выхода)..."
        tail -f server.log
        ;;
    3)
        echo "📋 Следим за обоими логами (Ctrl+C для выхода)..."
        tail -f logs/heat_up.log server.log
        ;;
    4)
        echo "🔴 Только ERRORS (Ctrl+C для выхода)..."
        tail -f logs/heat_up.log | grep --line-buffered "ERROR"
        ;;
    5)
        echo "⏰ Только scheduler INFO (Ctrl+C для выхода)..."
        tail -f logs/heat_up.log | grep --line-buffered "scheduler"
        ;;
    *)
        echo "❌ Неверный выбор"
        exit 1
        ;;
esac

