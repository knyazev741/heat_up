# Environment Variables Setup

Create a `.env` file in the project root with the following configuration:

```bash
# DeepSeek API Configuration (используется для всех LLM-агентов)
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here

# Telegram API Configuration
TELEGRAM_API_BASE_URL=https://api.knyazservice.com
TELEGRAM_API_KEY=optional-api-key-if-needed

# TGStat API Configuration
# Token for fetching real Telegram channels (optional, for manual channel updates)
TGSTAT_API_TOKEN=your-tgstat-token-here

# Session History Configuration
# How many days to keep session history (default: 30)
SESSION_HISTORY_DAYS=30

# Database path for session history
DATABASE_PATH=sessions.db

# Scheduler Configuration
SCHEDULER_ENABLED=true
SCHEDULER_CHECK_INTERVAL=1800  # seconds (30 minutes)

# Logging
LOG_LEVEL=INFO
```

## Required Variables

- `DEEPSEEK_API_KEY` - Your DeepSeek API key (required) - используется для ActionPlannerAgent, PersonaAgent, SearchAgent
- `TELEGRAM_API_BASE_URL` - Base URL for Telegram API server (required)

> **Note**: Проект мигрировал с OpenAI на DeepSeek API для экономии ~89% на API costs.
> См. [DEEPSEEK_MIGRATION.md](DEEPSEEK_MIGRATION.md) для подробностей.

## Optional Variables

- `TELEGRAM_API_KEY` - API key if your Telegram API server requires authentication
- `TGSTAT_API_TOKEN` - TGStat API token (only needed if you want to fetch new channels manually)
- `SESSION_HISTORY_DAYS` - Number of days to keep session history (default: 30)
- `DATABASE_PATH` - Path to SQLite database file (default: sessions.db)
- `SCHEDULER_ENABLED` - Enable automatic warmup scheduler (default: true)
- `SCHEDULER_CHECK_INTERVAL` - Scheduler check interval in seconds (default: 1800)
- `LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)

## Example Setup

```bash
# Copy the template
cp .env.example .env

# Edit with your values
nano .env
```

## Security Notes

⚠️ **NEVER commit the `.env` file to git!** It's already in `.gitignore`.

The TGStat token in this example is provided by the user but should be kept secure in production.

