#!/bin/bash

# Скрипт для массового добавления сессий в систему прогрева
# Использование: ./bulk_add_sessions.sh

API_URL="http://localhost:8080"

echo "=========================================="
echo "Массовое добавление сессий в Heat Up"
echo "=========================================="
echo ""

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
echo ""

# Спрашиваем сколько сессий добавить
read -p "Сколько сессий хочешь добавить? " session_count

if ! [[ "$session_count" =~ ^[0-9]+$ ]] || [ "$session_count" -lt 1 ]; then
    echo "❌ Некорректное число"
    exit 1
fi

echo ""
echo "Добавление $session_count сессий..."
echo ""

added_count=0
failed_count=0

for (( i=1; i<=session_count; i++ )); do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Сессия $i из $session_count"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    read -p "Session ID: " session_id
    
    if [ -z "$session_id" ]; then
        echo "⏭️  Пропускаем (пустой session_id)"
        ((failed_count++))
        continue
    fi
    
    read -p "Частота прогрева в день (Enter = авто от LLM, или укажи 2-7): " daily_count
    
    # Формируем JSON - всегда Russia, телефон автогенерируется
    if [ -z "$daily_count" ]; then
        json_data="{
            \"session_id\": \"$session_id\"
        }"
        echo "✨ Частота прогрева будет выбрана LLM на основе личности"
    else
        json_data="{
            \"session_id\": \"$session_id\",
            \"daily_activity_count\": $daily_count
        }"
        echo "📊 Частота прогрева: $daily_count раз/день (вручную)"
    fi
    echo "🇷🇺 Страна: Russia (автоматически)"
    
    echo ""
    echo "Добавляю сессию..."
    
    response=$(curl -s -X POST "$API_URL/accounts/add" \
        -H "Content-Type: application/json" \
        -d "$json_data")
    
    if echo "$response" | grep -q '"success":true'; then
        account_id=$(echo "$response" | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')
        persona_name=$(echo "$response" | grep -o '"persona_name":"[^"]*"' | cut -d'"' -f4)
        echo "✅ УСПЕШНО добавлен! Account ID: $account_id (Персона: $persona_name)"
        ((added_count++))
    else
        echo "❌ ОШИБКА при добавлении"
        echo "Ответ сервера: $response"
        ((failed_count++))
    fi
    
    echo ""
    
    # Пауза между добавлениями (чтобы не перегружать LLM)
    if [ $i -lt $session_count ]; then
        echo "⏳ Пауза 3 секунды..."
        sleep 3
        echo ""
    fi
done

echo "=========================================="
echo "ИТОГ"
echo "=========================================="
echo "✅ Добавлено: $added_count"
echo "❌ Ошибок: $failed_count"
echo ""

if [ $added_count -gt 0 ]; then
    echo "Проверить добавленные аккаунты:"
    echo "  curl $API_URL/accounts"
    echo ""
    echo "Запустить автоматический прогрев:"
    echo "  curl -X POST $API_URL/scheduler/start"
    echo ""
fi

echo "Готово! 🚀"

