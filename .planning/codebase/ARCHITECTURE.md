# Architecture

**Analysis Date:** 2026-03-27

## Pattern Overview

**Overall:** Event-driven pipeline with intent-based routing. The system receives user messages via Telegram, classifies them into intents, routes them to appropriate handlers, and responds with generated content or database operations.

**Key Characteristics:**
- Natural language intent classification (keyword-first, LLM-fallback)
- Task, reminder, routine, and decision management
- Vault-based note storage (markdown files)
- SQLite database for structured data
- Async-first throughout (Telegram API, LLM calls, database)
- Ollama integration for local LLM inference

## Layers

**Presentation / Bot Layer:**
- Purpose: Handles Telegram interactions, user input/output, command dispatch
- Location: `app/bot/`
- Contains: Command handlers, message router, scheduled jobs
- Depends on: Planning layer, Memory layer, LLM layer, Storage layer
- Used by: Telegram bot (entry point)

**Routing / Intent Layer:**
- Purpose: Classifies user intent and dispatches to appropriate handler
- Location: `app/bot/router.py`
- Contains: Route function that orchestrates intent classification and handler selection
- Depends on: LLM classifier, Planning layer, Memory layer, Storage layer
- Used by: Message handler

**Planning Layer:**
- Purpose: Manages tasks, reminders, routines, schedules, and reviews
- Location: `app/planning/`
- Contains: Task CRUD, reminder scheduling, routine management, daily/EOD summaries
- Depends on: Storage layer
- Used by: Router, commands

**Memory Layer:**
- Purpose: Manages user knowledge: vault (markdown files), retrieval, comparisons
- Location: `app/memory/`
- Contains: Vault I/O, content retrieval, decision tracking, comparison logic
- Depends on: Storage layer (for search context), filesystem (vault path)
- Used by: Router, response builders

**LLM Layer:**
- Purpose: Orchestrates language model calls (classification, generation, extraction)
- Location: `app/llm/`
- Contains: Classifier, Ollama client, prompts, response builders
- Depends on: Ollama (external HTTP service)
- Used by: Router, commands, planning layer (for summaries)

**Storage Layer:**
- Purpose: Persists structured data (tasks, reminders, decisions, preferences, logs)
- Location: `app/storage/`
- Contains: Database connection, async query helpers, schema definition, migrations
- Depends on: aiosqlite, SQLite
- Used by: All layers that need persistent data

**Config / Utils:**
- Purpose: Configuration, logging, time/text utilities
- Location: `app/config.py`, `app/utils/`
- Contains: Environment variables, logging setup, date/time helpers, text formatting
- Depends on: None (leaf layer)
- Used by: All layers

## Data Flow

**Standard Message Flow:**

1. User sends message via Telegram
2. `message_handler()` in `app/bot/handlers.py` receives Update
3. Message logged to `message_log` table
4. `route()` in `app/bot/router.py` called with message text
5. `classify()` in `app/llm/classifier.py` determines intent (keyword match first, LLM fallback)
6. Based on intent, route() selects handler:
   - `create_task` → `app/planning/tasks.create_task()`
   - `set_reminder` → `app/planning/schedules.create_reminder()`
   - `capture_note` → `app/memory/vault.write_inbox()`
   - `retrieval_query` → `app/memory/retrieval.retrieve_context()`
   - `list_tasks` → `app/planning/tasks.list_tasks()`
   - `draft_reply` → LLM generation
   - `answer` (default) → General LLM response
7. Handler executes, returns response string
8. `message_handler()` sends reply via Telegram

**Reminder Trigger Flow:**

1. `setup_jobs()` in `app/bot/jobs.py` registers repeating job (60s interval)
2. `check_reminders()` runs periodically
3. Queries `reminders` table for `status='pending' AND remind_at <= current_time`
4. For each due reminder, sends Telegram message and marks `status='sent'`

**Intent Extraction Flow:**

1. For intents requiring structured data (task, reminder, decision), LLM is called with extraction prompt
2. `_parse_kv()` helper extracts key:value pairs from LLM response
3. Values used to populate insert statements

**State Management:**

- **Persistent state:** Tasks, reminders, routines, decisions → SQLite tables
- **Session state:** `context.user_data` in handlers (e.g., pending drafts)
- **File state:** Vault markdown files (inbox, daily notes, decisions, projects)
- **Configuration state:** Environment variables (DB_PATH, VAULT_PATH, OLLAMA_BASE_URL, timezone)

## Key Abstractions

**Intent:**
- Purpose: Categorizes user intent to determine action
- Examples: `create_task`, `set_reminder`, `capture_note`, `retrieval_query`, `answer`
- Pattern: String enum validated against `VALID_TYPES` in `app/llm/classifier.py`

**Task:**
- Purpose: Represents a user action item
- Examples: `app/planning/tasks.py`
- Pattern: Row in `tasks` table with title, priority, due_date, status, project_id

**Reminder:**
- Purpose: Time-triggered notification tied to a task or standalone
- Examples: `app/planning/schedules.py`
- Pattern: Row in `reminders` table with title, remind_at, status (pending/sent)

**Vault:**
- Purpose: Markdown-based knowledge store, organized by category
- Examples: `app/memory/vault.py`, directories: inbox, daily, projects, decisions, snippets, routines, references, archive
- Pattern: Path-based hierarchy, files indexed by modification time

**Decision:**
- Purpose: Records significant decisions with context and reasoning
- Examples: `app/memory/vault.write_decision()`, stored in vault and indexed in `decision_index` table
- Pattern: Markdown file + database index row for search

**Routine:**
- Purpose: Recurring task or event
- Examples: `app/planning/routines.py`
- Pattern: Row in `routines` table with name, schedule_type (daily/weekly/monthly), schedule_value

## Entry Points

**Main Entry:**
- Location: `app/main.py`
- Triggers: `python -m app.main` or service startup
- Responsibilities:
  - Sets up logging
  - Runs database migrations
  - Initializes vault structure
  - Creates Telegram Application with handlers
  - Registers reminder checking job
  - Starts polling

**Message Handler:**
- Location: `app/bot/handlers.py::message_handler()`
- Triggers: User sends text message (not command) to Telegram bot
- Responsibilities:
  - Logs message to database
  - Calls router to get response
  - Sends reply via Telegram
  - Handles pending post confirmation flow

**Command Handlers:**
- Location: `app/bot/commands.py`
- Triggers: User sends `/command` to Telegram
- Responsibilities:
  - `/start` — health check, Ollama status
  - `/help` — usage instructions
  - `/task` — task management (add, list, today, done)
  - `/remind` — reminder creation
  - `/routine` — routine management
  - `/search` — cross-system search
  - `/decision` — decision logging
  - `/daily` — daily summary generation
  - `/eod` — end-of-day review
  - `/project` — project management
  - `/draft` — draft composition
  - `/post` — confirm and send draft

**Job Scheduler:**
- Location: `app/bot/jobs.py::setup_jobs()`
- Triggers: Application initialization
- Responsibilities: Registers `check_reminders` job (60s interval) for reminder dispatch

## Error Handling

**Strategy:** Try-catch at message handler level with user-facing fallback messages

**Patterns:**

- **LLM call failures:** `app/llm/ollama_client.generate()` catches TimeoutException, ConnectError, and generic exceptions, returns user-friendly messages ("The model took too long", "Cannot reach the language model", "Something went wrong")
- **Database errors:** Caught at handler level (e.g., `app/planning/tasks.complete_task()` returns boolean False if task not found)
- **Telegram send errors:** `app/bot/jobs.py::check_reminders()` wraps `context.bot.send_message()` in try-except, logs failure but continues to next reminder
- **Message handler errors:** Generic Exception caught, user receives "Something went wrong. Please try again."

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module
- Approach: `setup_logging()` in `app/utils/logging.py` configures StreamHandler (stdout) and FileHandler (`{LOG_PATH}/assistant.log`)
- Suppresses verbose libraries: httpx, telegram, apscheduler set to WARNING level

**Validation:**
- Intent classification: keywords checked first (regex patterns in `KEYWORD_MAP`), then LLM with fallback to "answer" if invalid
- Task extraction: `_parse_kv()` extracts key:value pairs, missing keys default to fallback values
- Reminder time: LLM extraction required; handler returns error if `when` field missing

**Authentication:**
- User filtering: `filters.User(user_id=TELEGRAM_USER_ID)` applied to all handlers in main entry point
- Only messages from configured TELEGRAM_USER_ID are processed

---

*Architecture analysis: 2026-03-27*
