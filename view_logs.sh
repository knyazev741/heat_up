#!/bin/bash
# Скрипт для удобного просмотра логов Heat Up сервиса

LOGFILE="logs/heat_up.log"

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   📋 Heat Up Service Logs Viewer${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

if [ ! -f "$LOGFILE" ]; then
    echo -e "${RED}❌ Log file not found: $LOGFILE${NC}"
    echo "Make sure the service has been started at least once."
    exit 1
fi

show_help() {
    echo "Доступные команды:"
    echo ""
    echo "  ./view_logs.sh              - Показать последние 50 строк"
    echo "  ./view_logs.sh all          - Показать весь файл"
    echo "  ./view_logs.sh live         - Live tail (следить в реальном времени)"
    echo "  ./view_logs.sh llm          - Показать только взаимодействия с LLM"
    echo "  ./view_logs.sh actions      - Показать только выполнение действий"
    echo "  ./view_logs.sh errors       - Показать только ошибки"
    echo "  ./view_logs.sh clear        - Очистить лог файл"
    echo "  ./view_logs.sh help         - Показать эту справку"
    echo ""
}

case "$1" in
    "all")
        echo -e "${GREEN}📄 Весь лог файл:${NC}"
        echo ""
        cat "$LOGFILE"
        ;;
    "live")
        echo -e "${GREEN}👁️  Live tail (Ctrl+C для выхода):${NC}"
        echo ""
        tail -f "$LOGFILE"
        ;;
    "llm")
        echo -e "${GREEN}🤖 LLM взаимодействия:${NC}"
        echo ""
        grep -E "(SENDING TO LLM|RECEIVED FROM LLM|SYSTEM PROMPT|USER PROMPT|RAW RESPONSE)" "$LOGFILE" | tail -100
        ;;
    "actions")
        echo -e "${GREEN}🎬 Выполнение действий:${NC}"
        echo ""
        grep -E "(EXECUTING ACTION|ACTION SUCCEEDED|ACTION FAILED)" "$LOGFILE" | tail -50
        ;;
    "errors")
        echo -e "${RED}❌ Ошибки:${NC}"
        echo ""
        grep -E "(ERROR|FAILED)" "$LOGFILE" | tail -30
        ;;
    "clear")
        echo -e "${YELLOW}⚠️  Очистка лог файла...${NC}"
        > "$LOGFILE"
        echo -e "${GREEN}✅ Лог файл очищен${NC}"
        ;;
    "help")
        show_help
        ;;
    *)
        echo -e "${GREEN}📋 Последние 50 строк:${NC}"
        echo ""
        tail -50 "$LOGFILE"
        echo ""
        echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
        echo -e "Для других опций используй: ${YELLOW}./view_logs.sh help${NC}"
        echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
        ;;
esac

