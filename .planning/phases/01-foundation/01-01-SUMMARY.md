---
phase: 01-foundation
plan: 01
subsystem: testing, routing
tags: [pytest, pytest-asyncio, regex, capability-refusal, router, keyword-matching]

# Dependency graph
requires: []
provides:
  - "pytest test infrastructure (pytest.ini, tests/__init__.py, tests/conftest.py)"
  - "5 passing unit tests covering FOUND-01 capability refusal"
  - "CAPABILITY_REFUSALS keyword dict in app/bot/router.py"
  - "_capability_refusal_check() helper function in router.py"
  - "REFUSAL_MESSAGE constant in router.py"
  - "intent=='answer' guard block in route() before build_answer()"
affects: [02-promptbuilder, 03-context-budget-manager]

# Tech tracking
tech-stack:
  added: [pytest==7.4.4, pytest-asyncio==0.23.8]
  patterns:
    - "Monkeypatch app.bot.router.{name} (imported name) not app.llm.module.{name} (source)"
    - "Pre-generation keyword guard: dict of regex patterns, re.search on lowercased text, gated on intent=='answer'"
    - "Test env stubs via os.environ.setdefault in conftest.py before any app imports"

key-files:
  created:
    - pytest.ini
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_refusal.py
  modified:
    - requirements.txt
    - app/bot/router.py

key-decisions:
  - "Monkeypatch target is app.bot.router.classify (the name as imported), not app.llm.classifier.classify — router uses from-import binding"
  - "today_str and create_reminder also mocked in test_non_answer_bypass to avoid tzdata/DB dependencies"
  - "CAPABILITY_REFUSALS guard placed after draft_reply block, before build_answer — preserves all existing intent dispatch"

patterns-established:
  - "Pattern: Test env stubs — set os.environ.setdefault stubs at top of conftest.py so app.config imports don't raise KeyError"
  - "Pattern: Patch imported names — always patch app.bot.router.X not the source module when testing router.py"
  - "Pattern: Pre-generation refusal — dict-of-lists keyword check in route() gated on intent=='answer', zero Ollama calls for refused messages"

requirements-completed: [FOUND-01]

# Metrics
duration: 10min
completed: 2026-03-28
---

# Phase 01 Plan 01: Foundation Summary

**Pre-generation capability refusal guard using CAPABILITY_REFUSALS keyword dict in route(), blocking code/math/research requests before any Ollama call, verified by 5 passing pytest-asyncio unit tests**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-28T16:10:37Z
- **Completed:** 2026-03-28T16:20:59Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Installed pytest 7.4.4 + pytest-asyncio 0.23.8 and wired pytest.ini with asyncio_mode=auto
- Wrote 5 unit tests covering all FOUND-01 acceptance criteria (code/math/research refusal + set_reminder bypass + retrieval bypass)
- Implemented CAPABILITY_REFUSALS dict and _capability_refusal_check() in router.py using re.search pattern (mirrors existing KEYWORD_MAP in classifier.py)
- Wired guard block in route() after draft_reply, before build_answer — guarantees zero generate() calls for refused messages

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 — Test scaffold** - `fb10eb3` (test)
2. **Task 2: Implement capability refusal guard** - `8f964f1` (feat)

_Note: TDD tasks — Task 1 = RED (failing stubs), Task 2 = GREEN (implementation makes all 5 pass)_

## Files Created/Modified
- `pytest.ini` - pytest configuration with asyncio_mode = auto
- `tests/__init__.py` - Package marker (empty)
- `tests/conftest.py` - Fixtures: env stubs, anyio_backend, in_memory_db
- `tests/test_refusal.py` - 5 unit tests covering FOUND-01 (code/math/research refusal + two bypass cases)
- `requirements.txt` - Added pytest==7.4.4 and pytest-asyncio==0.23.8
- `app/bot/router.py` - Added import re, CAPABILITY_REFUSALS dict, REFUSAL_MESSAGE, _capability_refusal_check(), and guard block in route()

## Decisions Made
- Monkeypatch target corrected from `app.llm.classifier.classify` to `app.bot.router.classify` — router.py uses `from app.llm.classifier import classify`, so the name is bound in the router module namespace. Patching the source module doesn't affect the already-bound name.
- Added `today_str` and `create_reminder` mocks to `test_non_answer_bypass` — set_reminder handler calls both before returning; mocking prevents tzdata (missing on Windows Python 3.13) and DB connection errors.
- Test env stubs (`TELEGRAM_TOKEN=test-token-stub`, `TELEGRAM_USER_ID=0`) set via `os.environ.setdefault` in conftest.py — app/config.py raises KeyError at import time without these.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Monkeypatch target corrected to imported namespace**
- **Found during:** Task 1 (test scaffold) — Task 2 verification
- **Issue:** Plan specified `app.llm.classifier.classify` as monkeypatch target. router.py uses `from app.llm.classifier import classify`, binding the function to `app.bot.router.classify`. Patching the source module has no effect on the already-bound name.
- **Fix:** Updated all 5 tests to patch `app.bot.router.classify` instead
- **Files modified:** tests/test_refusal.py
- **Verification:** Tests collected and ran (RED then GREEN after implementation)
- **Committed in:** fb10eb3, 8f964f1

**2. [Rule 3 - Blocking] Added TELEGRAM_TOKEN/TELEGRAM_USER_ID env stubs in conftest.py**
- **Found during:** Task 1, first pytest run
- **Issue:** `app/config.py` calls `os.environ["TELEGRAM_TOKEN"]` at module import time. Without a value, test collection raises KeyError before any test body runs.
- **Fix:** Added `os.environ.setdefault("TELEGRAM_TOKEN", "test-token-stub")` and `TELEGRAM_USER_ID=0` at top of conftest.py
- **Files modified:** tests/conftest.py
- **Verification:** All tests collected without ImportError
- **Committed in:** fb10eb3

**3. [Rule 3 - Blocking] Added today_str and create_reminder mocks in test_non_answer_bypass**
- **Found during:** Task 2, GREEN phase verification
- **Issue:** set_reminder handler calls `today_str()` (which uses `zoneinfo.ZoneInfo("UTC")` — fails on Windows Python 3.13 without tzdata package) and `create_reminder()` (hits real DB). Both are called before the handler returns.
- **Fix:** Added `monkeypatch.setattr("app.bot.router.today_str", lambda: "2026-03-28")` and `monkeypatch.setattr("app.bot.router.create_reminder", AsyncMock(return_value=1))`
- **Files modified:** tests/test_refusal.py
- **Verification:** test_non_answer_bypass passes; no tzdata or DB errors
- **Committed in:** 8f964f1

---

**Total deviations:** 3 auto-fixed (all Rule 3 — blocking)
**Impact on plan:** All auto-fixes were necessary for the test suite to run. No scope creep. FOUND-01 requirement fully met.

## Issues Encountered
- Windows Python 3.13 does not include tzdata package by default, causing `zoneinfo.ZoneInfo("UTC")` to raise ZoneInfoNotFoundError. Worked around with mock in tests; not a production concern (VPS runs Linux with system tzdata).

## User Setup Required
None - no external service configuration required beyond what was already in .env.example.

## Next Phase Readiness
- pytest infrastructure ready for Plan 01-02 (schema migration tests)
- conftest.py has in_memory_db fixture ready for DB-dependent tests
- app/bot/router.py capability refusal guard active and tested
- Plan 01-02 executor must READ existing conftest.py before editing (extend, not overwrite)

## Self-Check: PASSED
- tests/test_refusal.py: FOUND
- tests/conftest.py: FOUND
- tests/__init__.py: FOUND
- pytest.ini: FOUND
- app/bot/router.py: FOUND
- 01-01-SUMMARY.md: FOUND
- commit fb10eb3: FOUND
- commit 8f964f1: FOUND

---
*Phase: 01-foundation*
*Completed: 2026-03-28*
