#!/bin/bash

# Скрипт для добавления сессий из файла (неинтерактивный)
# Формат файла sessions.txt (каждая строка):
# session_id|phone_number|country|daily_count

API_URL="http://localhost:8080"
INPUT_FILE="${1:-sessions.txt}"

echo "=========================================="
echo "Добавление сессий из файла: $INPUT_FILE"
echo "=========================================="
echo ""

# Проверка что файл существует
if [ ! -f "$INPUT_FILE" ]; then
    echo "❌ Файл $INPUT_FILE не найден"
    echo ""
    echo "Создай файл sessions.txt с форматом:"
    echo "session_id|daily_count (опционально)"
    echo ""
    echo "Пример sessions.txt:"
    echo "session_001"
    echo "session_002|5"
    echo "session_003"
    echo ""
    exit 1
fi

# Проверка что сервер запущен
if ! curl -s "$API_URL/accounts" > /dev/null 2>&1; then
    echo "❌ ОШИБКА: Сервер не запущен на $API_URL"
    echo ""
    echo "Запусти сервер:"
    echo "  python main.py"
    echo ""
    exit 1
fi

echo "✅ Сервер доступен"
echo "✅ Файл найден: $INPUT_FILE"
echo ""

# Получаем список всех существующих сессий
echo "📋 Загружаем существующие сессии из базы..."
existing_sessions=$(curl -s "$API_URL/accounts?limit=10000" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4 | tr '\n' '|')
echo "✅ Загружено существующих сессий"
echo ""

added_count=0
skipped_count=0
failed_count=0
line_number=0

while IFS='|' read -r session_id daily_count || [ -n "$session_id" ]; do
    ((line_number++))
    
    # Пропускаем пустые строки и комментарии
    if [ -z "$session_id" ] || [[ "$session_id" == \#* ]]; then
        continue
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Строка $line_number: $session_id"
    
    # Проверяем, есть ли сессия уже в базе
    if [[ "|$existing_sessions|" == *"|$session_id|"* ]]; then
        echo "⏭️  ПРОПУЩЕНА: сессия уже в базе"
        ((skipped_count++))
        echo ""
        continue
    fi
    
    # Формируем JSON - если daily_count пустой, не включаем (LLM выберет)
    if [ -z "$daily_count" ]; then
        json_data="{
            \"session_id\": \"$session_id\"
        }"
        echo "  ✨ Частота: авто (LLM)"
    else
        json_data="{
            \"session_id\": \"$session_id\",
            \"daily_activity_count\": $daily_count
        }"
        echo "  📊 Частота: $daily_count раз/день"
    fi
    echo "  🇷🇺 Страна: Russia"
    
    response=$(curl -s -X POST "$API_URL/accounts/add" \
        -H "Content-Type: application/json" \
        -d "$json_data")
    
    if echo "$response" | grep -q '"success":true'; then
        account_id=$(echo "$response" | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')
        persona_name=$(echo "$response" | grep -o '"persona_name":"[^"]*"' | cut -d'"' -f4)
        echo "✅ УСПЕШНО! Account ID: $account_id (Персона: $persona_name)"
        ((added_count++))
    else
        echo "❌ ОШИБКА: $response"
        ((failed_count++))
    fi
    
    echo ""
    
    # Небольшая пауза между добавлениями
    sleep 2
    
done < "$INPUT_FILE"

echo "=========================================="
echo "ИТОГ"
echo "=========================================="
echo "✅ Добавлено: $added_count"
echo "⏭️  Пропущено: $skipped_count (уже в базе)"
echo "❌ Ошибок: $failed_count"
echo ""

if [ $added_count -gt 0 ]; then
    echo "Проверить аккаунты: ./check_accounts.sh"
    echo "Запустить прогрев: curl -X POST $API_URL/scheduler/start"
    echo ""
fi

echo "Готово! 🚀"

