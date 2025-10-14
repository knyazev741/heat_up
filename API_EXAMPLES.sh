#!/bin/bash

# API Examples for Warmup System
# Replace localhost:8080 with your actual host if needed

BASE_URL="http://localhost:8080"

echo "========================================"
echo "Heat Up - Warmup System API Examples"
echo "========================================"

# 1. Check service health
echo -e "\n1. Health check"
curl -s $BASE_URL/health | jq

# 2. Check scheduler status
echo -e "\n2. Scheduler status"
curl -s $BASE_URL/scheduler/status | jq

# 3. Add new account
echo -e "\n3. Add new account"
curl -s -X POST $BASE_URL/accounts/add \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "example_session_123",
    "phone_number": "+79991234567",
    "country": "Russia",
    "daily_activity_count": 3
  }' | jq

# Save account ID for next steps
# Manually set this after adding account
ACCOUNT_ID=1

# 4. Generate persona for account
echo -e "\n4. Generate persona"
curl -s -X POST $BASE_URL/accounts/$ACCOUNT_ID/generate-persona | jq

# 5. Find relevant chats for persona
echo -e "\n5. Find relevant chats"
curl -s -X POST $BASE_URL/accounts/$ACCOUNT_ID/refresh-chats | jq

# 6. Get account details
echo -e "\n6. Account details"
curl -s $BASE_URL/accounts/$ACCOUNT_ID | jq

# 7. Trigger warmup immediately
echo -e "\n7. Trigger warmup"
curl -s -X POST $BASE_URL/accounts/$ACCOUNT_ID/warmup-now | jq

# 8. Check account health
echo -e "\n8. Account health"
curl -s $BASE_URL/accounts/$ACCOUNT_ID/health | jq

# 9. List all accounts
echo -e "\n9. List all accounts"
curl -s $BASE_URL/accounts | jq

# 10. Get statistics
echo -e "\n10. System statistics"
curl -s $BASE_URL/statistics | jq

# 11. Get daily report
echo -e "\n11. Daily report"
curl -s $BASE_URL/statistics/daily | jq

# 12. Update account settings
echo -e "\n12. Update account settings"
curl -s -X POST $BASE_URL/accounts/$ACCOUNT_ID/update \
  -H "Content-Type: application/json" \
  -d '{
    "daily_activity_count": 4,
    "is_active": true
  }' | jq

# 13. Start scheduler (if not running)
echo -e "\n13. Start scheduler"
curl -s -X POST $BASE_URL/scheduler/start | jq

# 14. Stop scheduler
echo -e "\n14. Stop scheduler (uncomment to use)"
# curl -s -X POST $BASE_URL/scheduler/stop | jq

echo -e "\n========================================"
echo "Examples completed!"
echo "========================================"

