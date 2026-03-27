# Technology Stack

**Analysis Date:** 2026-03-27

## Languages

**Primary:**
- Python 3.x - All application code, bot logic, LLM integration, data processing

## Runtime

**Environment:**
- Python 3.x (specified via `.venv/bin/python` in systemd service)

**Package Manager:**
- pip
- Lockfile: `requirements.txt` present

## Frameworks

**Core:**
- python-telegram-bot 21.3 - Telegram Bot API wrapper with job queue support
- httpx 0.27.0 - Async HTTP client for external API calls

**Database:**
- aiosqlite 0.20.0 - Async SQLite3 wrapper for database operations

**Environment:**
- python-dotenv 1.0.1 - .env file loading for configuration

## Key Dependencies

**Critical:**
- python-telegram-bot[job-queue] 21.3 - Provides entire bot framework with scheduled job execution for reminders
- httpx 0.27.0 - Async HTTP client used for Ollama LLM requests and web search via DuckDuckGo
- aiosqlite 0.20.0 - Database access layer for SQLite persistence

**Infrastructure:**
- No external infrastructure SDKs (AWS, GCP, etc.)

## Configuration

**Environment:**
Configuration loaded via `python-dotenv` from `.env` file (example at `.env.example`):
- `TELEGRAM_TOKEN` - Bot authentication token (required)
- `TELEGRAM_USER_ID` - User ID for access control (required)
- `OLLAMA_BASE_URL` - Ollama API endpoint (default: `http://localhost:11434`)
- `OLLAMA_MODEL` - LLM model name (default: `qwen3:4b`)
- `BASE_DIR` - Base installation directory (default: `/opt/assistant` on Linux, `C:/Tintu, the Assistant` on Windows)
- `TIMEZONE` - Server timezone (default: `UTC`)

**Build:**
- No build configuration; pure Python application
- Systemd service file at `systemd/assistant.service` for production deployment

## Platform Requirements

**Development:**
- Python 3.x with pip
- Ollama 0.x running locally (for LLM inference)
- Telegram Bot API access (requires token)

**Production:**
- Linux system with systemd (primary target: `/opt/assistant`)
- Python 3.x virtualenv
- Ollama service running and accessible
- Telegram Bot API access
- Network connectivity to Telegram API and Ollama endpoint

## Database

**Type:**
- SQLite3 with Write-Ahead Logging (WAL mode enabled)
- Foreign key constraints enabled

**Location:**
- `{BASE_DIR}/data/assistant.db`

**Tables:**
- preferences, projects, tasks, reminders, routines, events
- conversation_summaries, decision_index, message_log

## Data Storage

**File Storage:**
- Local filesystem only
- Vault directory structure at `{BASE_DIR}/vault/` with subdirectories:
  - inbox, daily, projects, decisions, snippets, routines, references, archive
  - Markdown files for notes and decision records

**Logs:**
- Application logs at `{BASE_DIR}/data/logs/`
- Systemd journal via StandardOutput=journal

**Cache:**
- Cache directory at `{BASE_DIR}/data/cache/` (created but usage varies)

## Entry Points

**Application:**
- `app/main.py` - Main entry point, runs telegram bot polling loop
- Started via systemd service: `/opt/assistant/venv/bin/python -m app.main`

---

*Stack analysis: 2026-03-27*
