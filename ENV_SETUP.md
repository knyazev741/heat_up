# Environment Variables Setup

Create a `.env` file in the project root with the following configuration:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=sk-proj-your-openai-api-key-here

# Telegram API Configuration
TELEGRAM_API_BASE_URL=http://localhost:8000
TELEGRAM_API_KEY=optional-api-key-if-needed

# TGStat API Configuration
# Token for fetching real Telegram channels (optional, for manual channel updates)
TGSTAT_API_TOKEN=2539dfbdf80afd5c45d0c8f86cc9d21a

# Session History Configuration
# How many days to keep session history (default: 30)
SESSION_HISTORY_DAYS=30

# Database path for session history
DATABASE_PATH=sessions.db

# Logging
LOG_LEVEL=INFO
```

## Required Variables

- `OPENAI_API_KEY` - Your OpenAI API key (required)
- `TELEGRAM_API_BASE_URL` - Base URL for Telegram API server (required)

## Optional Variables

- `TELEGRAM_API_KEY` - API key if your Telegram API server requires authentication
- `TGSTAT_API_TOKEN` - TGStat API token (only needed if you want to fetch new channels manually)
- `SESSION_HISTORY_DAYS` - Number of days to keep session history (default: 30)
- `DATABASE_PATH` - Path to SQLite database file (default: sessions.db)
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

