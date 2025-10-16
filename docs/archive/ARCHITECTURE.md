# 🏗️ Heat Up - Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           External Client                            │
│                    (HTTP POST /warmup/{session_id})                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         FastAPI Server (main.py)                     │
│                                                                       │
│  ┌─────────────────────┐              ┌──────────────────────┐      │
│  │  /warmup/{id}       │              │ /warmup-sync/{id}    │      │
│  │  (async)            │              │ (sync)               │      │
│  │  - Quick response   │              │ - Full report        │      │
│  │  - Background tasks │              │ - Waits completion   │      │
│  └─────────┬───────────┘              └──────────┬───────────┘      │
│            └───────────────┬──────────────────────┘                  │
│                            │                                         │
└────────────────────────────┼─────────────────────────────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
┌───────────────────────────┐   ┌────────────────────────┐
│  LLM Agent (llm_agent.py) │   │ Telegram API Client    │
│                           │   │ (telegram_client.py)   │
│  ┌────────────────────┐   │   │                        │
│  │ GPT-4o-mini        │   │   │  ┌─────────────────┐   │
│  │ (OpenAI API)       │   │   │  │ join_chat()     │   │
│  └─────────┬──────────┘   │   │  ├─────────────────┤   │
│            │              │   │  │ send_message()  │   │
│            ▼              │   │  ├─────────────────┤   │
│  ┌────────────────────┐   │   │  │ invoke_raw()    │   │
│  │ Generate Actions   │   │   │  ├─────────────────┤   │
│  │ - 3-7 steps       │   │   │  │ get_dialogs()   │   │
│  │ - Diverse channels│   │   │  └─────────────────┘   │
│  │ - Natural timing  │   │   │                        │
│  └─────────┬──────────┘   │   └────────┬───────────────┘
│            │              │            │
│            ▼              │            │
│  ┌────────────────────┐   │            │
│  │ Validate & Sanitize│   │            │
│  │ - Check actions    │   │            │
│  │ - Limit durations  │   │            │
│  └─────────┬──────────┘   │            │
└────────────┼──────────────┘            │
             │                           │
             └───────────┬───────────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │ Action Executor       │
             │ (executor.py)         │
             │                       │
             │ For each action:      │
             │  1. Execute           │
             │  2. Log result        │
             │  3. Natural delay     │
             │  4. Next action       │
             │                       │
             │ Returns summary       │
             └───────────┬───────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │ External Telegram API │
             │ (from openapi.json)   │
             │                       │
             │ - Session management  │
             │ - RPC methods         │
             │ - Chat operations     │
             └───────────────────────┘
```

## Component Details

### 1. FastAPI Server (`main.py`)

**Responsibilities:**
- HTTP request handling
- Input validation
- Response formatting
- Background task management
- Lifecycle management

**Endpoints:**
- `POST /warmup/{session_id}` - Async warmup
- `POST /warmup-sync/{session_id}` - Sync warmup
- `GET /health` - Health check
- `GET /` - Service info

**Key Features:**
- Async/await support
- Background tasks via BackgroundTasks
- Automatic OpenAPI documentation
- Structured logging

### 2. LLM Agent (`llm_agent.py`)

**Responsibilities:**
- Generate action plans via GPT-4o-mini
- Validate LLM output
- Provide fallback strategies
- Ensure diversity

**Key Functions:**
```python
generate_action_plan(session_id) -> List[Action]
- Calls OpenAI API
- Parses JSON response
- Validates actions
- Returns plan or fallback

_validate_actions(actions) -> List[Action]
- Check action types
- Validate parameters
- Limit durations

_get_fallback_actions() -> List[Action]
- Safe default plan
- Used when LLM fails
```

**LLM Prompt Strategy:**
- Provides channel pool
- Requests 3-7 actions
- Encourages diversity
- High temperature (1.0) for variety
- Uses GPT-4o-mini for cost-effectiveness

### 3. Telegram API Client (`telegram_client.py`)

**Responsibilities:**
- Wrap Telegram API calls
- Handle authentication
- Error handling
- Request/response parsing

**Key Methods:**
```python
join_chat(session_id, chat_id)
- Join channel/chat
- Returns success/error

send_message(session_id, chat_id, text)
- Send message
- Optional silent mode

invoke_raw(session_id, query)
- Execute arbitrary TL query
- Full flexibility

get_dialogs(session_id)
- Get user's chats
- Used for "browsing" simulation
```

**Features:**
- Async HTTP client (httpx)
- Automatic retries
- Timeout handling
- Detailed error logging

### 4. Action Executor (`executor.py`)

**Responsibilities:**
- Execute action sequences
- Natural timing
- Progress tracking
- Error collection

**Execution Flow:**
```
For each action in plan:
  1. Log start
  2. Execute action
     - join_channel: Call API
     - read_messages: Get dialogs + wait
     - idle: Just wait
  3. Record result
  4. Natural delay (3-10s, random)
  5. Next action

Return execution summary
```

**Natural Delays:**
- Base: 3-10 seconds random
- Occasional longer: +5-10 seconds (10% chance)
- Simulates human behavior

### 5. Configuration (`config.py`)

**Contents:**
```python
Settings:
- API keys
- Base URLs
- Log level

CHANNEL_POOL:
- 20+ channels
- Diverse categories
- Username + description

ACTION_DELAYS:
- Min/max between actions
- Min/max read times
```

## Data Flow

### Typical Request Flow:

```
1. Client Request
   POST /warmup/abc123
   
2. FastAPI Handler
   - Validate session_id
   - Call LLM agent
   
3. LLM Generation
   - Build prompt with channels
   - Call OpenAI API
   - Parse JSON response
   
4. Validation
   - Check action types
   - Validate parameters
   - Apply limits
   
5. Execution (Background or Sync)
   - For each action:
     a. Execute via Telegram client
     b. Wait natural delay
   - Collect results
   
6. Response
   Async: Return plan immediately
   Sync: Return full summary

7. Logging
   - Request received
   - Plan generated
   - Each action executed
   - Final summary
```

### Example Action Plan:

```json
{
  "session_id": "abc123",
  "action_plan": [
    {
      "action": "join_channel",
      "channel_username": "@telegram",
      "reason": "Official updates"
    },
    {
      "action": "read_messages", 
      "channel_username": "@telegram",
      "duration_seconds": 8,
      "reason": "Browse posts"
    },
    {
      "action": "idle",
      "duration_seconds": 5,
      "reason": "Short break"
    }
  ]
}
```

### Execution Timeline:

```
t=0s:    Join @telegram
t=3s:    Wait 3s delay
t=3s:    Start reading @telegram
t=11s:   Finish reading (8s duration)
t=14s:   Wait 3s delay  
t=14s:   Start idle
t=19s:   Finish idle (5s duration)
t=22s:   Wait 3s delay
t=22s:   Complete - return summary
```

## Error Handling

### Graceful Degradation:

```
Level 1: LLM fails
└─> Use fallback action plan

Level 2: Action fails
└─> Log error, continue with next action

Level 3: Telegram API error
└─> Record in results, don't crash

Level 4: Critical error
└─> Return error response, log details
```

### Retry Strategy:

- **LLM calls**: No retry (expensive), use fallback
- **Telegram API**: Configured retries (default: 10)
- **HTTP requests**: httpx default retry logic

## Scalability Considerations

### Current Limitations:
- Single-threaded per request
- No persistent storage
- Synchronous LLM calls

### Scaling Options:

**Horizontal Scaling:**
```bash
# Multiple workers
uvicorn main:app --workers 4

# Load balancer
nginx -> worker1, worker2, worker3, worker4
```

**Async Optimization:**
```python
# Batch LLM calls
plans = await asyncio.gather(*[
    agent.generate_action_plan(sid) 
    for sid in session_ids
])

# Parallel execution
await asyncio.gather(*[
    executor.execute_action_plan(sid, plan)
    for sid, plan in zip(session_ids, plans)
])
```

**Caching:**
- Cache channel list
- Cache LLM responses (with variation)
- Redis for distributed cache

### Production Recommendations:

1. **Add Database:**
   - Store execution history
   - Track success rates
   - Analyze patterns

2. **Add Queue:**
   - Celery/RQ for task queue
   - Handle spikes in requests
   - Retry failed tasks

3. **Add Monitoring:**
   - Prometheus metrics
   - Grafana dashboards
   - Error alerting

4. **Add Rate Limiting:**
   - Per IP
   - Per session
   - API key quotas

## Security Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ HTTPS
       ▼
┌──────────────┐
│ Rate Limiter │ ← slowapi/nginx
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   FastAPI    │ ← Input validation
└──────┬───────┘
       │
       ├─────────────────┐
       │                 │
       ▼                 ▼
┌─────────────┐   ┌──────────────┐
│ OpenAI API  │   │ Telegram API │
│ (API key)   │   │ (API key)    │
└─────────────┘   └──────────────┘
```

**Security Measures:**
- ✅ Environment variables for secrets
- ✅ Input validation (pydantic)
- ✅ Timeouts on all requests
- ✅ Error message sanitization
- ⚠️ No authentication (add if needed)
- ⚠️ No rate limiting (add if needed)

## Testing Strategy

### Unit Tests:
```python
tests/
├── test_llm_agent.py
│   ├── test_generate_plan
│   ├── test_validation
│   └── test_fallback
├── test_executor.py
│   ├── test_execute_action
│   ├── test_delays
│   └── test_error_handling
├── test_telegram_client.py
│   ├── test_join_chat
│   └── test_send_message
└── test_api.py
    ├── test_warmup_endpoint
    └── test_health_endpoint
```

### Integration Tests:
```python
# End-to-end test
async def test_full_warmup():
    response = await client.post("/warmup/test_id")
    assert response.status_code == 200
    assert "action_plan" in response.json()
```

### Load Tests:
```bash
# Using locust or k6
k6 run load_test.js
```

## Monitoring Points

### Key Metrics:
- Request rate (req/s)
- Response time (p50, p95, p99)
- Success rate (%)
- LLM call time (ms)
- Telegram API call time (ms)
- Error rate by type

### Log Levels:
```
DEBUG: Delays, LLM responses
INFO:  Requests, action execution
WARN:  Failed actions, fallbacks
ERROR: API errors, critical failures
```

### Health Checks:
```bash
# Liveness (is it running?)
GET /health

# Readiness (can it serve?)
GET /health
- Check LLM agent initialized
- Check Telegram client ready
```

---

**Architecture Version**: 1.0.0  
**Last Updated**: 2024-10-10  
**Status**: Production-ready MVP

