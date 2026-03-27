# Codebase Structure

**Analysis Date:** 2026-03-27

## Directory Layout

```
C:/Tintu, the Assistant/
├── app/                    # Main application code
│   ├── bot/               # Telegram bot handlers and routing
│   │   ├── commands.py    # Command handlers (/start, /task, /remind, etc.)
│   │   ├── handlers.py    # Message handler (main entry point for user text)
│   │   ├── jobs.py        # Scheduled jobs (reminder checker)
│   │   ├── router.py      # Intent-based message router
│   │   └── __init__.py
│   ├── llm/               # Language model integration
│   │   ├── classifier.py  # Intent classification (keyword + LLM)
│   │   ├── ollama_client.py # HTTP client for Ollama inference
│   │   ├── prompts.py     # System/extraction prompts
│   │   ├── response_builder.py # Response generation patterns
│   │   └── __init__.py
│   ├── memory/            # Knowledge and memory management
│   │   ├── vault.py       # Markdown vault I/O
│   │   ├── retrieval.py   # Context retrieval from tasks/decisions/vault
│   │   ├── comparison.py  # Compare current against prior state
│   │   ├── summarizer.py  # Conversation summarization
│   │   ├── citations.py   # Citation formatting
│   │   └── __init__.py
│   ├── planning/          # Task, reminder, routine management
│   │   ├── tasks.py       # Task CRUD and querying
│   │   ├── schedules.py   # Reminder CRUD and querying
│   │   ├── routines.py    # Routine CRUD and querying
│   │   ├── reviews.py     # Daily summary and EOD review generation
│   │   └── __init__.py
│   ├── storage/           # Database and persistence
│   │   ├── db.py          # Database connection and async query helpers
│   │   ├── models.py      # Database schema (CREATE TABLE statements)
│   │   ├── migrations.py  # Database setup/migration runner
│   │   └── __init__.py
│   ├── utils/             # Utilities
│   │   ├── logging.py     # Logging configuration
│   │   ├── time.py        # Date/time helpers
│   │   ├── text.py        # Text formatting (task lines, reminder lines)
│   │   └── __init__.py
│   ├── web/               # Web integration (search)
│   │   ├── search.py      # External search integration
│   │   └── __init__.py
│   ├── config.py          # Environment variables and paths
│   ├── main.py            # Application entry point
│   └── __init__.py
├── prompts/               # Prompt templates (external files)
├── scripts/               # Utility scripts
├── systemd/               # Systemd service files
├── .planning/             # Planning and analysis documents
│   └── codebase/         # Codebase analysis (this directory)
├── .claude/               # Claude workspace metadata
└── .git/                  # Version control
```

## Directory Purposes

**app/**
- Purpose: Main application package, organized by functional domain
- Contains: All business logic, handlers, and integrations
- Key files: `main.py` (entry), `config.py` (configuration)

**app/bot/**
- Purpose: Telegram bot layer — command parsing, message handling, job scheduling
- Contains: Telegram handler functions, routing logic
- Key files: `handlers.py` (message dispatcher), `router.py` (intent-based routing), `commands.py` (slash commands), `jobs.py` (background tasks)

**app/llm/**
- Purpose: Language model abstraction — classification, generation, prompt management
- Contains: Ollama HTTP client, intent classifier, response builders
- Key files: `classifier.py` (intent detection), `ollama_client.py` (LLM API), `prompts.py` (all prompts), `response_builder.py` (response patterns)

**app/memory/**
- Purpose: Knowledge storage and retrieval — vault management, context retrieval, comparisons
- Contains: Vault file I/O, search, decision tracking, summarization
- Key files: `vault.py` (markdown storage), `retrieval.py` (context gathering), `comparison.py` (delta analysis)

**app/planning/**
- Purpose: Task/reminder/routine management and reviews
- Contains: CRUD operations for planning entities, summary generation
- Key files: `tasks.py` (task operations), `schedules.py` (reminder operations), `routines.py` (routine operations), `reviews.py` (daily/EOD generation)

**app/storage/**
- Purpose: Database persistence layer
- Contains: Async SQLite wrapper, schema, migrations
- Key files: `db.py` (connection pool and query helpers), `models.py` (schema definition)

**app/utils/**
- Purpose: Shared utilities
- Contains: Logging, date/time, text formatting
- Key files: `logging.py` (logging setup), `time.py` (date helpers), `text.py` (formatting)

**app/web/**
- Purpose: External web integration (placeholder for search, external APIs)
- Contains: Search integration points
- Key files: `search.py` (web search wrapper)

**prompts/**
- Purpose: Stored prompt templates
- Contains: System prompts, extraction prompts (external to code for easy editing)
- Note: Path defined in `app/config.PROMPTS_PATH`

**scripts/**
- Purpose: Utility and automation scripts
- Contains: Database tools, setup scripts, etc.

**systemd/**
- Purpose: Service deployment configuration
- Contains: Systemd unit files for running as system service

## Key File Locations

**Entry Points:**
- `app/main.py`: Main entry point — initializes app, sets up handlers, starts polling
- `app/bot/handlers.py::message_handler()`: Receives every user message
- `app/bot/commands.py`: Command handlers (slash commands)

**Configuration:**
- `app/config.py`: Environment variables and file paths

**Core Logic:**
- `app/bot/router.py`: Intent classification and dispatch
- `app/llm/classifier.py`: Intent detection (keyword → LLM fallback)
- `app/planning/tasks.py`: Task management
- `app/memory/vault.py`: Knowledge storage
- `app/storage/db.py`: Database access

**Database:**
- `app/storage/models.py`: Schema definition (CREATE TABLE)
- `app/storage/migrations.py`: Schema initialization

**Testing:**
- No test files present in repository (see CONCERNS.md)

## Naming Conventions

**Files:**
- Lowercase with underscores: `message_handler.py`, `ollama_client.py`
- Functional modules: `classifier.py` (classification logic), `router.py` (routing logic), `vault.py` (vault operations)
- CRUD modules: `tasks.py`, `schedules.py`, `routines.py` (named after domain entity)

**Directories:**
- Lowercase plural for feature areas: `app/bot/`, `app/llm/`, `app/memory/`, `app/planning/`, `app/storage/`, `app/utils/`
- Special: `prompts/` (prompt storage), `scripts/` (utilities), `systemd/` (deployment)

**Functions:**
- Lowercase with underscores: `message_handler()`, `create_task()`, `list_tasks()`
- Async prefixed with `async def`: all database and Telegram operations
- Verb-noun pattern for CRUD: `create_task()`, `list_tasks()`, `complete_task()`, `update_task_status()`
- Underscore prefix for internal helpers: `_parse_kv()` (private key-value parser)

**Classes/Types:**
- Not heavily used; logic is functional
- Enums: `VALID_TYPES` (intent set), `KEYWORD_MAP` (intent keyword map)
- Constants: UPPERCASE for config constants (TELEGRAM_TOKEN, OLLAMA_MODEL, VAULT_DIRS)

**Variables:**
- camelCase for local variables (intent, message, tasks, reminder_id)
- Underscore for internal state (context.user_data["pending_post"])

## Where to Add New Code

**New Intent Handler:**
1. Add intent name to `VALID_TYPES` in `app/llm/classifier.py`
2. Add keyword patterns to `KEYWORD_MAP` in `app/llm/classifier.py`
3. Add intent case in `app/bot/router.py::route()` function with handler logic or call to planning/memory module
4. If extraction needed, add prompt to `app/llm/prompts.py` and call `generate(PROMPT.format(...))`

**New Planning Feature (Tasks/Reminders/Routines):**
1. Add schema to `app/storage/models.py`
2. Create CRUD module: `app/planning/{feature}.py` with async functions (create_, list_, update_, delete_ patterns)
3. Call from `app/bot/router.py` or `app/bot/commands.py`

**New Command:**
1. Add async handler function to `app/bot/commands.py`
2. Register in `app/main.py` with `app.add_handler(CommandHandler("name", handler_func, filters=user_filter))`

**Vault Feature (Notes, Decisions, etc.):**
1. Add directory to `VAULT_DIRS` in `app/memory/vault.py` if needed
2. Add write/read functions to `app/memory/vault.py`
3. Add indexing to database if searchable (e.g., decision_index table)
4. Call from `app/bot/router.py` or command handler

**Utility Function:**
- Shared: `app/utils/{domain}.py` (e.g., `time.py` for date functions, `text.py` for formatting)
- Domain-specific: Within the module that uses it (e.g., internal `_parse_kv()` in `router.py` and `commands.py`)

**LLM Prompt:**
1. Add to `app/llm/prompts.py` as module-level constant
2. Reference in handler via `PROMPT_NAME.format(...)`
3. Or store externally in `prompts/` directory and load at runtime

## Special Directories

**Vault (configured path, typically `/opt/assistant/vault/`):**
- Purpose: User's personal knowledge base, organized by category
- Generated: Yes (created by `ensure_vault_structure()` on startup)
- Committed: No (user data, outside repo)
- Directories:
  - `inbox/` — Quick captured notes
  - `daily/` — Daily notes and summaries
  - `projects/` — Project-specific files (overview, tasks, notes, decisions, phase)
  - `decisions/` — Decision logs
  - `snippets/` — Code/text snippets
  - `routines/` — Routine descriptions
  - `references/` — Reference material
  - `archive/` — Archived content

**Database (configured path, typically `/opt/assistant/data/assistant.db`):**
- Purpose: Structured data storage (tasks, reminders, routines, decisions, preferences, message log)
- Generated: Yes (created by migrations on startup)
- Committed: No (persistent data, outside repo)

**Logs (configured path, typically `/opt/assistant/data/logs/`):**
- Purpose: Application logs
- Generated: Yes (created by logging setup)
- Committed: No (runtime logs, outside repo)

**Cache (configured path, typically `/opt/assistant/data/cache/`):**
- Purpose: Temporary cache (currently unused)
- Generated: Yes (created by config)
- Committed: No (ephemeral data)

**.planning/codebase/**
- Purpose: Codebase analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: By orchestrator tools
- Committed: Yes (part of repo)

---

*Structure analysis: 2026-03-27*
