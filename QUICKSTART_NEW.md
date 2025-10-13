# 🚀 Quick Start - New Features

This guide covers the new TGStat integration and session history features.

## What's New?

1. **Real Channels** - 30+ verified Telegram channels instead of fake ones
2. **Session History** - SQLite database tracking all warmup actions
3. **Smart Behavior** - LLM adapts based on whether user is new or returning

## Quick Test

### 1. Start the Service

```bash
cd /Users/knyaz/heat_up
./venv/bin/python main.py
```

Service will automatically:
- ✅ Initialize SQLite database (`sessions.db`)
- ✅ Load 32 real channels from `channels_data.json`
- ✅ Start background cleanup task

### 2. First Warmup (New User)

```bash
curl -X POST "http://localhost:8080/warmup/test_user_1"
```

**Expected:**
- LLM receives "first time user" prompt
- Generates 3-7 actions using real channels
- All successful actions saved to database

### 3. Second Warmup (Returning User)

```bash
# Wait a moment, then run again with same session_id
curl -X POST "http://localhost:8080/warmup/test_user_1"
```

**Expected:**
- LLM receives "returning user" prompt with history
- Mentions previously joined channels
- Shows time since last activity

### 4. Check History

```bash
curl "http://localhost:8080/sessions/test_user_1/history"
```

**Response shows:**
- Summary: is_new, total_actions, joined_channels, last_activity
- Full history: all actions with timestamps

## Channel Pool

Check loaded channels:
```bash
./venv/bin/python -c "from config import CHANNEL_POOL; print(f'{len(CHANNEL_POOL)} channels loaded')"
```

View channel categories:
```bash
./venv/bin/python -c "from config import CHANNEL_POOL; from collections import Counter; cats = Counter(ch['category'] for ch in CHANNEL_POOL); print(dict(cats))"
```

## Database Operations

```python
from database import *

# Initialize
init_database()

# Check if session is new
is_new = is_new_session("test_user_1")
print(f"Is new: {is_new}")

# Get history
history = get_session_history("test_user_1", days=30)
print(f"Actions: {len(history)}")

# Get summary
summary = get_session_summary("test_user_1")
print(f"Joined channels: {summary['joined_channels']}")
```

## Verifying Dynamic Prompts

```python
from llm_agent import ActionPlannerAgent

agent = ActionPlannerAgent()

# New user prompt
prompt1 = agent._build_prompt("new_session_id")
print("NEW USER PROMPT:")
print(prompt1[:300])

# After some actions, check returning user prompt
prompt2 = agent._build_prompt("test_user_1")  # Has history
print("\nRETURNING USER PROMPT:")
print(prompt2[:300])
```

## Common Issues

### No channels loaded
**Solution:** Ensure `channels_data.json` exists in project root

### Database errors
**Solution:** Delete `sessions.db` and restart service (auto-recreates)

### History not working
**Solution:** Check that actions complete successfully (check logs)

## Next Steps

1. Review full documentation: `TGSTAT_INTEGRATION.md`
2. Check implementation details: `IMPLEMENTATION_SUMMARY.md`
3. Configure environment: `ENV_SETUP.md`
4. Read updated README: `README.md`

## Quick Stats

- ✅ 32 total channels (2 verified + 30 real)
- ✅ 11 categories
- ✅ SQLite session tracking
- ✅ Dynamic prompt generation
- ✅ Auto cleanup (30 days retention)
- ✅ New history API endpoint

---

**Ready to use!** The service is fully functional with all new features integrated.

