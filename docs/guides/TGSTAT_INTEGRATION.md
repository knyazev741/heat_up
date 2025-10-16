# TGStat Integration & Session History

## Overview

This document describes the TGStat integration and session history tracking features added to the Heat Up service.

## Features

### 1. Real Channel Pool from TGStat

Instead of using hardcoded, potentially non-existent channels, the system now uses real Telegram channels sourced from TGStat API.

**Channel Data:**
- 30+ real, verified Telegram channels
- Diverse categories: News, Technology, Programming, Crypto, Business, Science, Entertainment, Sports, Music, Lifestyle
- Stored locally in `channels_data.json` to minimize API calls
- Fallback to verified channels (@durov, @telegram) if file not found

**File:** `channels_data.json`
```json
[
  {
    "username": "@rt_russian",
    "description": "RT на русском",
    "category": "News",
    "subscribers": 1500000,
    "tgstat_url": "https://t.me/rt_russian"
  },
  ...
]
```

### 2. Session History Tracking

All warmup actions are now stored in a SQLite database, enabling dynamic behavior based on user history.

**Database:** `sessions.db`

**Schema:**
```sql
CREATE TABLE session_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    action_data TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

**Tracked Actions:**
- `join_channel` - When user joins a channel
- `read_messages` - When user reads messages
- `idle` - When user takes a break

### 3. Dynamic Prompts

The LLM prompt now adapts based on whether the session is new or returning.

**New User Prompt:**
```
You are simulating natural behavior for a new Telegram user who just logged in for the first time.
This is your first time using Telegram, so explore channels that interest you naturally.
```

**Returning User Prompt:**
```
You are simulating a returning Telegram user who is coming back online.

Previous activity summary:
- Last active: 2 days ago
- Total previous actions: 15
- Previously joined channels: @durov, @telegram, @crypto, @habr_com

You're back for another session and should continue natural, varied behavior.
```

## API Endpoints

### New Endpoint: Get Session History

**GET** `/sessions/{session_id}/history?days=30`

Returns the session history and summary.

**Response:**
```json
{
  "session_id": "abc123",
  "summary": {
    "is_new": false,
    "total_actions": 15,
    "joined_channels": ["@durov", "@telegram", "@crypto"],
    "last_activity": "2024-01-10T12:34:56",
    "recent_actions": [...]
  },
  "history": [
    {
      "id": 1,
      "session_id": "abc123",
      "action_type": "join_channel",
      "action_data": {"channel_username": "@durov"},
      "timestamp": "2024-01-10T12:30:00"
    },
    ...
  ]
}
```

## Configuration

### Environment Variables

Add to `.env`:

```bash
# TGStat API Token (for manual channel fetching)
TGSTAT_API_TOKEN=your_token_here

# Session history retention (days)
SESSION_HISTORY_DAYS=30

# Database path
DATABASE_PATH=sessions.db
```

### Settings

Updated `config.py` with:
- `tgstat_api_token` - TGStat API token
- `session_history_days` - How long to keep history (default: 30 days)
- `database_path` - SQLite database file path

## Usage

### Manual Channel Fetching

If you have an active TGStat subscription, you can fetch new channels:

```bash
python tgstat_fetcher.py
```

This will:
1. Query TGStat API for channels in various categories
2. Deduplicate and format channel data
3. Save to `channels_data.json`

**Note:** The free TGStat tier has limited API calls (50/month). The fetcher is designed to be run manually when needed, not automatically.

### Running Warmup

The warmup process now automatically:
1. Checks if session is new or returning
2. Generates appropriate prompt with history context
3. Creates diverse action plan using real channels
4. Executes actions and saves them to database
5. Uses history in future warmups

**Example:**
```bash
# First warmup (new user)
curl -X POST http://localhost:8080/warmup/session_abc123

# Response includes actions for a new user exploring Telegram

# Second warmup (returning user)
curl -X POST http://localhost:8080/warmup/session_abc123

# Response adapts based on previous actions and joined channels
```

### Checking Session History

```bash
curl http://localhost:8080/sessions/session_abc123/history
```

## Files

### New Files

- **`tgstat_fetcher.py`** - Fetches channels from TGStat API
- **`database.py`** - SQLite session history management
- **`channels_data.json`** - Cached real channel data
- **`sessions.db`** - SQLite database (auto-created)
- **`test_integration.py`** - Integration tests
- **`TGSTAT_INTEGRATION.md`** - This documentation

### Modified Files

- **`config.py`** - Added channel loading from JSON, new settings
- **`llm_agent.py`** - Dynamic prompts based on session history
- **`executor.py`** - Saves actions to database after execution
- **`main.py`** - Database initialization, cleanup task, history endpoint

## Database Management

### Automatic Cleanup

The service automatically cleans up old session history daily. Records older than `SESSION_HISTORY_DAYS` (default: 30 days) are deleted.

### Manual Database Operations

```python
from database import *

# Initialize database
init_database()

# Get session history
history = get_session_history("session_id", days=30)

# Check if session is new
is_new = is_new_session("session_id")

# Get summary
summary = get_session_summary("session_id")

# Clean up old records
cleanup_old_history(days=30)

# Get all active sessions
sessions = get_all_sessions(days=30)
```

## Testing

Run integration tests:

```bash
python test_integration.py
```

Tests verify:
- Database initialization and operations
- Channel pool loading (verified + fetched channels)
- Dynamic prompt generation (new vs returning users)
- Session history tracking

## Architecture Changes

### Flow with Session History

```
1. Client Request → POST /warmup/{session_id}
2. Check Database → Is session new or returning?
3. Build Dynamic Prompt
   - New: "first time user" prompt
   - Returning: "back online, previously did X" prompt
4. LLM Generation → Uses real channels from channels_data.json
5. Execute Actions → Telegram API
6. Save to Database → Track all successful actions
7. Return Response

Next warmup for same session uses history!
```

## Troubleshooting

### No channels loaded

**Problem:** Channel pool only has 2 verified channels.

**Solution:** Ensure `channels_data.json` exists. If not, create it with real channels or run `tgstat_fetcher.py` if you have TGStat API access.

### Database errors

**Problem:** SQLite errors or missing tables.

**Solution:** Delete `sessions.db` and restart the service. Database will be recreated automatically.

### TGStat API errors

**Problem:** "no_active_subscription" error when running fetcher.

**Solution:** TGStat requires a paid subscription for the API. Use the provided `channels_data.json` with pre-populated real channels, or manually add more channels to the file.

## Future Improvements

1. **More Channel Sources:** Integrate with other channel directories
2. **Channel Validation:** Periodically check if channels still exist
3. **Advanced Analytics:** Track warmup success rates, optimal patterns
4. **Channel Recommendations:** ML-based channel suggestions based on history
5. **Export/Import:** Backup and restore session history

## Credits

- **TGStat API:** [https://api.tgstat.ru](https://api.tgstat.ru)
- Real channel data sourced from TGStat directory

