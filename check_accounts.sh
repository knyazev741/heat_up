#!/bin/bash

# Быстрая проверка статуса всех аккаунтов

API_URL="http://localhost:8000"

echo "=========================================="
echo "Статус аккаунтов в системе прогрева"
echo "=========================================="
echo ""

# Проверка что сервер запущен
if ! curl -s "$API_URL/accounts" > /dev/null 2>&1; then
    echo "❌ ОШИБКА: Сервер не запущен на $API_URL"
    echo ""
    exit 1
fi

# Получаем список аккаунтов
echo "📋 Список аккаунтов:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

accounts=$(curl -s "$API_URL/accounts")

if echo "$accounts" | grep -q '\[\]'; then
    echo "⚠️  Нет добавленных аккаунтов"
    echo ""
    echo "Добавь аккаунты:"
    echo "  ./bulk_add_sessions.sh"
    echo ""
    exit 0
fi

# Парсим и выводим красиво
echo "$accounts" | python3 -c "
import sys
import json

try:
    accounts = json.load(sys.stdin)
    for acc in accounts:
        status = '✅' if acc.get('is_active') else '❌'
        print(f\"{status} ID: {acc.get('account_id'):3d} | {acc.get('phone_number'):15s} | Stage {acc.get('stage'):2d}/14 | Active: {acc.get('daily_activity_count')}x/day\")
except:
    print('Ошибка парсинга JSON')
"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Статистика
echo "📊 Общая статистика:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

stats=$(curl -s "$API_URL/statistics")

echo "$stats" | python3 -c "
import sys
import json

try:
    stats = json.load(sys.stdin)
    print(f\"Всего аккаунтов: {stats.get('total_accounts', 0)}\")
    print(f\"Активных: {stats.get('active_accounts', 0)}\")
    print(f\"Сессий прогрева: {stats.get('total_warmup_sessions', 0)}\")
    print(f\"Действий выполнено: {stats.get('total_actions_performed', 0)}\")
    
    stages = stats.get('accounts_by_stage', {})
    if stages:
        print(f\"\\nПо этапам:\")
        for stage, count in sorted(stages.items(), key=lambda x: int(x[0])):
            print(f\"  Stage {stage}: {count} аккаунтов\")
except Exception as e:
    print(f'Ошибка: {e}')
"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Статус scheduler
echo "⏰ Статус планировщика:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

scheduler_status=$(curl -s "$API_URL/scheduler/status")

if echo "$scheduler_status" | grep -q '"running":true'; then
    echo "✅ Планировщик РАБОТАЕТ"
    
    echo "$scheduler_status" | python3 -c "
import sys
import json
from datetime import datetime

try:
    data = json.load(sys.stdin)
    print(f\"Аккаунтов отслеживается: {data.get('accounts_tracked', 0)}\")
    
    next_runs = data.get('next_runs', [])
    if next_runs:
        print(f\"\\nБлижайшие запуски:\")
        for run in next_runs[:5]:
            acc_id = run.get('account_id')
            phone = run.get('phone_number', 'N/A')
            next_time = run.get('next_run_time', 'N/A')
            print(f\"  Account {acc_id} ({phone}): {next_time}\")
except Exception as e:
    pass
"
else
    echo "⚠️  Планировщик НЕ РАБОТАЕТ"
    echo ""
    echo "Запустить:"
    echo "  curl -X POST $API_URL/scheduler/start"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Полезные команды:"
echo "  ./monitor.sh              - мониторинг"
echo "  tail -f logs/heat_up.log  - логи в реальном времени"
echo "  curl $API_URL/accounts/1  - детали аккаунта #1"
echo ""

