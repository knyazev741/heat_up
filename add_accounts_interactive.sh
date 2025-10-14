#!/bin/bash

# Интерактивное добавление аккаунтов

BASE_URL="http://localhost:8080"

echo "================================="
echo "  Добавление аккаунтов для прогрева"
echo "================================="
echo ""

# Проверка, что сервис работает
curl -s $BASE_URL/health > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Сервис не доступен! Запусти: python main.py"
    exit 1
fi

echo "✓ Сервис работает"
echo ""

# Количество аккаунтов
read -p "Сколько аккаунтов добавить? " COUNT

for i in $(seq 1 $COUNT); do
    echo ""
    echo "--- Аккаунт $i/$COUNT ---"
    
    read -p "Session ID: " SESSION_ID
    read -p "Номер телефона (например +79991234567): " PHONE
    read -p "Страна (Enter для автоопределения): " COUNTRY
    read -p "Прогревов в день (2-5, Enter для 3): " DAILY_COUNT
    
    # Default values
    if [ -z "$DAILY_COUNT" ]; then
        DAILY_COUNT=3
    fi
    
    # Build JSON
    if [ -z "$COUNTRY" ]; then
        JSON="{\"session_id\":\"$SESSION_ID\",\"phone_number\":\"$PHONE\",\"daily_activity_count\":$DAILY_COUNT}"
    else
        JSON="{\"session_id\":\"$SESSION_ID\",\"phone_number\":\"$PHONE\",\"country\":\"$COUNTRY\",\"daily_activity_count\":$DAILY_COUNT}"
    fi
    
    echo ""
    echo "Добавляю аккаунт..."
    
    RESPONSE=$(curl -s -X POST $BASE_URL/accounts/add \
        -H "Content-Type: application/json" \
        -d "$JSON")
    
    SUCCESS=$(echo $RESPONSE | jq -r '.success // false')
    
    if [ "$SUCCESS" == "true" ]; then
        ACCOUNT_ID=$(echo $RESPONSE | jq -r '.data.id')
        echo "✅ Аккаунт добавлен! ID: $ACCOUNT_ID"
    else
        echo "❌ Ошибка при добавлении:"
        echo $RESPONSE | jq -r '.detail // .message // .'
    fi
done

echo ""
echo "================================="
echo "✓ Добавление завершено!"
echo ""
echo "Проверь статус:"
echo "  curl http://localhost:8080/accounts | jq"
echo ""
echo "Или запусти мониторинг:"
echo "  ./monitor.sh"
echo ""

