# Coding Conventions

**Analysis Date:** 2026-03-27

## Naming Patterns

**Files:**
- Module files: `lowercase_with_underscores.py` (e.g., `classifier.py`, `ollama_client.py`, `response_builder.py`)
- Organized by feature/domain in directory structure: `app/bot/`, `app/llm/`, `app/planning/`, `app/storage/`, `app/memory/`, `app/utils/`
- Files are focused, single-responsibility (one class/few functions per file)

**Functions:**
- All functions use `snake_case` naming
- Async functions are clearly named with `async def` keyword, no special prefix
- Helper/internal functions prefixed with `_` when private to module (e.g., `_parse_kv()`, `_parse_key_value()`)
- Examples: `classify()`, `create_task()`, `list_tasks()`, `write_inbox()`, `fetch_all()`

**Variables:**
- All variables use `snake_case`
- Dictionary keys consistently use `snake_case` when data is structured (e.g., `task['status']`, `reminder['remind_at']`)
- Parameters with optional/union types use Python 3.10+ syntax (e.g., `str | None`, `int | None`)

**Types:**
- Consistent use of modern Python type hints (PEP 604 syntax)
- Union types: `str | None` (not `Optional[str]`)
- Generic collection types: `list[dict]`, `list[str]`, `dict[str, str]`
- Return types always annotated on function definitions
- Parameter types always annotated

## Code Style

**Formatting:**
- No explicit formatter configured (no Black, Prettier, or similar in codebase)
- Follows Python PEP 8 conventions informally
- Line length appears unbounded but generally readable (80-120 character lines)
- Spacing: 4-space indentation (Python standard)

**Linting:**
- No linting configuration detected (no `.eslintrc`, `pyproject.toml` with tool config, `pylintrc`, etc.)
- Code follows PEP 8 spirit without formal enforcement

## Import Organization

**Order:**
1. Standard library imports (e.g., `import logging`, `from pathlib import Path`, `from datetime import datetime`)
2. Third-party imports (e.g., `import httpx`, `from telegram import Update`, `import aiosqlite`)
3. Local app imports (e.g., `from app.config import`, `from app.storage.db import`)

**Path Aliases:**
- No path aliases configured (no `@` shortcuts in `tsconfig.json` or Python import aliases)
- All imports use absolute paths from app root: `from app.bot.router import route`
- All imports reference the `app` package explicitly

**Examples from codebase:**
```python
# From app/bot/router.py
import logging
from app.llm.classifier import classify
from app.llm.ollama_client import generate
from app.bot.router import route

# From app/storage/db.py
import aiosqlite
from app.config import DB_PATH
```

## Error Handling

**Patterns:**
- Broad exception handling with `except Exception as e:` followed by logging (not aggressive try-catch)
- Exceptions logged at ERROR level with context information
- User-facing error messages are generic/user-friendly, not technical
- Format: `logger.error(f"Context message: {e}", exc_info=True)` or simpler variations
- No custom exception classes detected; relies on built-in exceptions

**Examples:**
```python
# From app/bot/handlers.py
try:
    await message.reply_chat_action("typing")
    response = await route(text)
    await message.reply_text(response, parse_mode="Markdown")
except Exception as e:
    logger.error(f"Handler error: {e}", exc_info=True)
    await message.reply_text("Something went wrong. Please try again.")

# From app/llm/ollama_client.py
try:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        response.raise_for_status()
        return response.json().get("response", "").strip()
except httpx.TimeoutException:
    logger.error("Ollama request timed out")
    return "The model took too long to respond. Please try again."
except httpx.ConnectError:
    logger.error("Cannot connect to Ollama")
    return "Cannot reach the language model. Is Ollama running?"
except Exception as e:
    logger.error(f"Ollama error: {e}")
    return "Something went wrong with the language model."
```

## Logging

**Framework:** `logging` (Python standard library)

**Setup:** Centralized in `app/utils/logging.py`
- Function: `setup_logging()` configures root logger
- Location: `app/utils/logging.py` lines 6-20
- Output: stdout + file to `LOG_PATH / "assistant.log"` (from config)
- Format: `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`
- Suppresses verbose logs from third-party libraries (httpx, telegram, apscheduler set to WARNING)

**Patterns:**
- All modules use `logger = logging.getLogger(__name__)` pattern (always at module level)
- INFO level for normal operation: task creation, reminders sent, system ready messages
- DEBUG level for detailed flow: `logger.debug(f"Keyword classified: {intent}")`
- WARNING level for unexpected but recoverable issues: `logger.warning(f"Classification fallback for: {message[:60]!r}")`
- ERROR level for exceptions with context: `logger.error(f"Handler error: {e}", exc_info=True)`
- Log messages include context (ids, truncated text, status)

**Examples:**
```python
# From app/bot/router.py
logger.info(f"Intent: {intent} | message: {message[:60]!r}")

# From app/llm/classifier.py
logger.debug(f"Keyword classified: {intent}")
logger.debug(f"LLM classified: {result}")
logger.warning(f"Classification fallback for: {message[:60]!r}")

# From app/bot/jobs.py
logger.info(f"Sent reminder id={reminder['id']}")
logger.error(f"Failed to send reminder {reminder['id']}: {e}")
```

## Comments

**When to Comment:**
- Minimal comments observed in codebase (pragmatic approach)
- Comments used to mark logical sections within large functions (e.g., `# ── Capture note ──────────────────────────────────────────────────────────`)
- Diagram-style section separators used in `app/bot/router.py` to delineate intent handlers

**JSDoc/TSDoc:**
- No docstrings or type documentation found (Python docstrings not used)
- Types are expressed through inline type hints instead
- Function names are self-documenting (e.g., `create_task()`, `list_pending_reminders()`)

## Function Design

**Size:**
- Small to medium functions (5-50 lines typical)
- Largest files: `app/bot/commands.py` (373 lines) and `app/bot/router.py` (199 lines) - these are routers with many conditional branches
- Most utility functions 10-30 lines
- Async functions consistently follow async/await patterns

**Parameters:**
- Functions take 1-5 parameters typically
- Optional parameters use defaults (e.g., `max_results: int = 10`)
- Keyword-only arguments not heavily used, but parameter order is logical
- Type hints required for all parameters

**Return Values:**
- Single return type per function
- Async functions return awaitable values
- Return None explicitly when appropriate (not implicit)
- Return values always type-hinted with `->` syntax

## Module Design

**Exports:**
- No `__all__` lists found in codebase
- Modules export functions and classes implicitly (no barrel/index files)
- Imports are explicit: `from app.bot.router import route`

**Barrel Files:**
- Not used; each module/package imports exactly what it needs
- `app/` subdirectories have `__init__.py` but they're empty or minimal

**Organization by Feature:**
- `app/bot/` - Telegram bot integration and message routing
- `app/llm/` - Language model and LLM interaction
- `app/planning/` - Task, reminder, routine, review management
- `app/storage/` - Database layer and schema
- `app/memory/` - Vault (file-based memory), retrieval, comparison, citations
- `app/utils/` - Utilities: logging, time, text formatting
- `app/config.py` - Centralized configuration from env vars

## Async Patterns

**Consistency:**
- All I/O operations (database, HTTP, file) are async using `async def` and `await`
- Async context managers: `async with await get_db() as db:` (opening database connection)
- Job queue integration: APScheduler integration via `telegram.ext.JobQueue`
- Callback functions in job handlers are async

**Examples:**
```python
# From app/storage/db.py
async def fetchone(query: str, params: tuple = ()) -> dict | None:
    async with await get_db() as db:
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

# From app/bot/jobs.py
async def check_reminders(context):
    user_id = context.job.data
    current_time = now().strftime("%Y-%m-%d %H:%M")
    due = await get_due_reminders(current_time)
```

## String Formatting

**Style:**
- f-strings used consistently for string interpolation
- Examples: `f"Intent: {intent} | message: {message[:60]!r}"`
- Triple-quoted strings for multi-line prompts (prompts.py)
- Markdown formatting in user-facing strings: `*bold*`, `_italic_`, backticks for code

**Examples:**
```python
# From app/bot/router.py
reply = f"✅ Task added: *{title}*"

# From app/llm/prompts.py (multi-line)
SYSTEM_PROMPT = """\
You are a private planning and memory assistant...\
"""
```

---

*Convention analysis: 2026-03-27*
