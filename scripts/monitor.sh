#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8080"

echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}  Heat Up - Мониторинг прогрева${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""

# 1. Проверка health сервиса
echo -e "${YELLOW}[1] Статус сервиса${NC}"
HEALTH=$(curl -s $BASE_URL/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Сервис работает${NC}"
else
    echo -e "${RED}✗ Сервис не доступен!${NC}"
    exit 1
fi
echo ""

# 2. Статус scheduler
echo -e "${YELLOW}[2] Статус scheduler${NC}"
SCHEDULER=$(curl -s $BASE_URL/scheduler/status | jq -r '.is_running')
if [ "$SCHEDULER" == "true" ]; then
    echo -e "${GREEN}✓ Scheduler запущен${NC}"
    ACCOUNTS=$(curl -s $BASE_URL/scheduler/status | jq -r '.accounts_scheduled')
    echo "  Аккаунтов в планировщике: $ACCOUNTS"
else
    echo -e "${RED}✗ Scheduler остановлен${NC}"
fi
echo ""

# 3. Общая статистика
echo -e "${YELLOW}[3] Общая статистика${NC}"
STATS=$(curl -s $BASE_URL/statistics)
TOTAL=$(echo $STATS | jq -r '.total_accounts')
ACTIVE=$(echo $STATS | jq -r '.active_accounts')
FROZEN=$(echo $STATS | jq -r '.frozen_accounts')
BANNED=$(echo $STATS | jq -r '.banned_accounts')
AVG_STAGE=$(echo $STATS | jq -r '.average_warmup_stage')

echo "  Всего аккаунтов: $TOTAL"
echo -e "  Активных: ${GREEN}$ACTIVE${NC}"
if [ "$FROZEN" -gt 0 ]; then
    echo -e "  Замороженных: ${RED}$FROZEN${NC}"
else
    echo -e "  Замороженных: ${GREEN}0${NC}"
fi
if [ "$BANNED" -gt 0 ]; then
    echo -e "  Забаненных: ${RED}$BANNED${NC}"
else
    echo -e "  Забаненных: ${GREEN}0${NC}"
fi
echo "  Средняя стадия прогрева: $AVG_STAGE"
echo ""

# 4. Список аккаунтов
echo -e "${YELLOW}[4] Список аккаунтов${NC}"
ACCOUNTS_DATA=$(curl -s $BASE_URL/accounts)
echo "$ACCOUNTS_DATA" | jq -r '.accounts[] | "  ID: \(.id) | Телефон: \(.phone_number) | Стадия: \(.warmup_stage) | Прогревов: \(.total_warmups) | Активен: \(.is_active)"'
echo ""

# 5. Health check каждого аккаунта
echo -e "${YELLOW}[5] Health Score аккаунтов${NC}"
ACCOUNT_IDS=$(echo "$ACCOUNTS_DATA" | jq -r '.accounts[].id')

for ID in $ACCOUNT_IDS; do
    HEALTH=$(curl -s $BASE_URL/accounts/$ID/health)
    SCORE=$(echo $HEALTH | jq -r '.health_score')
    STATUS=$(echo $HEALTH | jq -r '.health_status')
    ISSUES_COUNT=$(echo $HEALTH | jq -r '.issues | length')
    
    if [ "$STATUS" == "excellent" ] || [ "$STATUS" == "good" ]; then
        COLOR=$GREEN
    elif [ "$STATUS" == "fair" ]; then
        COLOR=$YELLOW
    else
        COLOR=$RED
    fi
    
    echo -e "  Account $ID: ${COLOR}$SCORE ($STATUS)${NC}"
    
    if [ "$ISSUES_COUNT" -gt 0 ]; then
        echo "    Проблемы:"
        echo $HEALTH | jq -r '.issues[] | "      - \(.)"'
    fi
done
echo ""

# 6. Ежедневный отчет
echo -e "${YELLOW}[6] Отчет за сегодня${NC}"
DAILY=$(curl -s $BASE_URL/statistics/daily)
WARMED=$(echo $DAILY | jq -r '.accounts_warmed_today')
ACTIONS=$(echo $DAILY | jq -r '.total_actions_today')
SUCCESS=$(echo $DAILY | jq -r '.successful_actions')
FAILED=$(echo $DAILY | jq -r '.failed_actions')
SUCCESS_RATE=$(echo $DAILY | jq -r '.success_rate')

echo "  Прогрето аккаунтов: $WARMED"
echo "  Всего действий: $ACTIONS"
echo "  Успешных: $SUCCESS"
echo "  Неудачных: $FAILED"
echo "  Success rate: $SUCCESS_RATE%"
echo ""

# 7. Последние логи
echo -e "${YELLOW}[7] Последние 10 строк лога${NC}"
if [ -f "logs/heat_up.log" ]; then
    tail -10 logs/heat_up.log | while IFS= read -r line; do
        if echo "$line" | grep -q "ERROR"; then
            echo -e "${RED}$line${NC}"
        elif echo "$line" | grep -q "WARNING"; then
            echo -e "${YELLOW}$line${NC}"
        elif echo "$line" | grep -q "✅\|SUCCESS"; then
            echo -e "${GREEN}$line${NC}"
        else
            echo "$line"
        fi
    done
else
    echo "  Лог-файл не найден"
fi
echo ""

echo -e "${BLUE}=================================${NC}"
echo "Мониторинг завершен: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "Полезные команды:"
echo "  Добавить аккаунт:    curl -X POST $BASE_URL/accounts/add -H 'Content-Type: application/json' -d '{...}'"
echo "  Запустить прогрев:   curl -X POST $BASE_URL/accounts/{ID}/warmup-now"
echo "  Смотреть логи:       tail -f logs/heat_up.log"
echo "  Остановить scheduler: curl -X POST $BASE_URL/scheduler/stop"
echo ""

