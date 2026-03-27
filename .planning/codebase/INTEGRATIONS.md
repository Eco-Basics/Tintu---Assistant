# External Integrations

**Analysis Date:** 2026-03-27

## APIs & External Services

**Messaging Platform:**
- Telegram Bot API - Primary interface for user interaction
  - SDK/Client: `python-telegram-bot[job-queue]` 21.3
  - Auth: `TELEGRAM_TOKEN` environment variable
  - Implementation: Polling-based message handler in `app/bot/handlers.py`

**Language Model Inference:**
- Ollama - Local LLM inference API
  - SDK/Client: `httpx` 0.27.0 (async HTTP calls)
  - Endpoint: `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
  - Model: `OLLAMA_MODEL` (default: `qwen3:4b`)
  - Client code: `app/llm/ollama_client.py`
  - Requests: POST to `/api/generate` and GET to `/api/tags` for health checks

**Web Search:**
- DuckDuckGo Instant Answer API - Optional web search capability
  - SDK/Client: `httpx` 0.27.0
  - Endpoint: `https://api.duckduckgo.com/`
  - Implementation: `app/web/search.py` (lightweight integration, V1 best-effort support)
  - No authentication required

## Data Storage

**Databases:**
- SQLite3 local database
  - Connection: `{BASE_DIR}/data/assistant.db`
  - Client: `aiosqlite` 0.20.0
  - Schema: `app/storage/models.py` (8 tables: preferences, projects, tasks, reminders, routines, events, conversation_summaries, decision_index, message_log)

**File Storage:**
- Local filesystem only
  - Vault path: `{BASE_DIR}/vault/` with subdirectories for inbox, daily notes, projects, decisions, etc.
  - Implementation: `app/memory/vault.py` uses `pathlib.Path` for all file I/O

**Caching:**
- Local directory: `{BASE_DIR}/data/cache/` (allocated but usage varies by module)

## Authentication & Identity

**Auth Provider:**
- Telegram Bot API - Custom integration
  - Implementation: User ID filter in `app/main.py` line 31 (`filters.User(user_id=TELEGRAM_USER_ID)`)
  - Single-user authorization (specified via `TELEGRAM_USER_ID`)
  - No other auth systems (OAuth, SAML, etc.)

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service

**Logs:**
- Python logging module with file and systemd journal output
  - Setup in `app/utils/logging.py`
  - Output to `{BASE_DIR}/data/logs/` and systemd journal
  - Systemd configuration: `StandardOutput=journal`, `StandardError=journal`

## CI/CD & Deployment

**Hosting:**
- Linux VPS (systemd-based deployment)
- Primary target: `/opt/assistant/`
- Systemd service files: `systemd/assistant.service`, `systemd/assistant-friend.service`, `systemd/assistant-mithu.service`

**CI Pipeline:**
- None - Manual deployment via systemd service

## Environment Configuration

**Required env vars:**
- `TELEGRAM_TOKEN` - Bot authentication token (no default)
- `TELEGRAM_USER_ID` - User ID for single-user authorization (no default)

**Optional env vars with defaults:**
- `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- `OLLAMA_MODEL` (default: `qwen3:4b`)
- `BASE_DIR` (default: `/opt/assistant`)
- `TIMEZONE` (default: `UTC`)

**Secrets location:**
- `.env` file (not committed to git, see `.env.example` template)
- Systemd EnvironmentFile: `/opt/assistant/.env`

## Webhooks & Callbacks

**Incoming:**
- Telegram message webhooks - Handled via polling in `app/main.py` (not webhook-based)
- No HTTP webhook endpoints exposed

**Outgoing:**
- Telegram Bot API calls only (sending messages, chat actions)
- DuckDuckGo search requests (search queries)
- Ollama inference requests (prompt generation)

## Service Dependencies

**Ollama:**
- Type: External service dependency
- Status check: `app/llm/ollama_client.py` line 34-40 (`check_ollama()` function)
- Systemd dependency: Systemd service requests `After=ollama.service` and `Wants=ollama.service`
- Fallback: Returns error message if unavailable

**Telegram:**
- Type: Required external service
- Always required for operation
- No fallback; bot cannot start without valid `TELEGRAM_TOKEN`

---

*Integration audit: 2026-03-27*
