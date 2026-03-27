# Testing Patterns

**Analysis Date:** 2026-03-27

## Test Framework

**Status:** No testing framework detected. Zero test files found in codebase.

- Test runner: Not configured
- Test assertion library: None
- pytest/unittest: Not present
- conftest.py: Does not exist
- No test directories (tests/, test/, spec/)

**Run Commands:**
```bash
# No test suite configured
# No test runs available
```

## Test File Organization

**Location:** Not applicable — no tests present

**Naming:** Not applicable — no tests present

**Structure:** Not applicable — no tests present

## Testing Gaps

**What's NOT tested:**
- `app/bot/router.py` - Core message routing and intent handling (200+ lines)
- `app/bot/handlers.py` - Telegram message handler and reply logic
- `app/bot/commands.py` - Command implementations (373 lines)
- `app/llm/classifier.py` - Intent classification via keyword matching and LLM
- `app/llm/ollama_client.py` - HTTP calls to Ollama API, error handling
- `app/planning/tasks.py` - Task CRUD operations against database
- `app/planning/schedules.py` - Reminder CRUD operations
- `app/planning/reviews.py` - Daily summary and EOD review generation
- `app/memory/vault.py` - File system operations (read/write markdown files)
- `app/memory/retrieval.py` - Context retrieval and database queries
- `app/storage/db.py` - Database abstraction layer
- `app/storage/migrations.py` - Schema creation

**Critical untested areas:**
- Async database operations (aiosqlite wrappers in `app/storage/db.py`)
- Exception handling paths (no tests for API failures, timeouts, database errors)
- Telegram bot integration and message routing
- Prompt generation and LLM response parsing
- File I/O and vault operations
- Type handling and data validation

## Mock & Fixture Patterns

**Not applicable:** No tests exist in codebase. No mocking framework or test fixtures configured.

## Coverage

**Requirements:** Not enforced — no coverage tracking

**View Coverage:** Not available

**Current state:** 0% (no tests)

## Recommendations for Testing

**Priority areas to test (by importance):**

1. **Database layer (`app/storage/db.py`, `app/planning/tasks.py`, `app/planning/schedules.py`)**
   - Risk: Data corruption or loss
   - Impact: Application-critical functionality
   - Approach: Unit tests with SQLite in-memory database or fixtures

2. **Async error handling in `app/llm/ollama_client.py`**
   - Risk: Silent failures or poor user feedback
   - Impact: User gets "something went wrong" without context
   - Approach: Async test harness mocking httpx responses

3. **Message routing logic in `app/bot/router.py`**
   - Risk: Messages routed to wrong handler
   - Impact: User confusion, data in wrong place
   - Approach: Parameterized tests for each intent type

4. **File I/O in `app/memory/vault.py`**
   - Risk: File corruption, permission errors, encoding issues
   - Impact: Lost notes and decisions
   - Approach: Temporary directory fixtures, path operations testing

5. **Telegram handler integration in `app/bot/handlers.py`**
   - Risk: Unhandled exceptions block message processing
   - Impact: Bot becomes unresponsive
   - Approach: Mock telegram.Update and context types

## Suggested Testing Strategy

**Framework recommendation:** pytest with pytest-asyncio
- Lightweight, Python-native
- Good async support
- Easy parameterization for testing multiple intents

**Example structure** (not currently present):

```python
# tests/test_storage.py (example of what should exist)
import pytest
from app.storage.db import execute, fetchone, fetchall

@pytest.mark.asyncio
async def test_execute_creates_row():
    # Setup: create in-memory db
    # Execute: insert row
    # Assert: row exists
    pass

@pytest.mark.asyncio
async def test_fetchone_returns_dict():
    # Setup: insert test data
    # Execute: fetchone()
    # Assert: returns dict-like row
    pass
```

```python
# tests/test_router.py (example of what should exist)
import pytest
from app.bot.router import route

@pytest.mark.asyncio
@pytest.mark.parametrize("message,expected_intent", [
    ("add a task to review", "create_task"),
    ("remind me Friday", "set_reminder"),
    ("save this note", "capture_note"),
])
async def test_route_intent_classification(message, expected_intent):
    # Would require mocking classify() to avoid LLM calls
    pass
```

## Current Test Absence Impact

**Manual testing only:**
- No regression detection — changes could break existing functionality silently
- No CI/CD gates — untested code commits to main
- No code coverage visibility — unclear which code paths are used
- Fragile refactoring — large functions (router.py, commands.py) difficult to safely modify

**Error handling untested:**
- Ollama timeout behavior unknown
- Database constraint violations untested
- File permission errors on vault operations untested
- Telegram rate limiting unhandled

## Type Hints (As Substitute for Some Testing)

While no test framework exists, the codebase does use comprehensive type hints throughout:

**Examples of type-driven design:**
- `async def fetchall(query: str, params: tuple = ()) -> list[dict]:`
- `async def create_task(title: str, due_date: str = "", priority: int = 0) -> int:`
- `def search_vault(query: str, max_results: int = 10) -> list[dict]:`

Type hints provide some level of compile-time checking (if using mypy or pyright), but do NOT substitute for runtime testing.

**To enable static type checking add:**
```bash
pip install mypy
mypy app/  # Run static type checker
```

---

*Testing analysis: 2026-03-27*

**Note:** This codebase would benefit significantly from a test suite. Given the async nature of the application, database operations, and external API calls, tests are strongly recommended before further development or refactoring.
