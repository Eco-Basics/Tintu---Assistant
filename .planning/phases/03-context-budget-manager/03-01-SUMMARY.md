---
phase: 03-context-budget-manager
plan: 01
subsystem: database
tags: [sqlite, aiosqlite, pytest, pytest-asyncio, schema, migrations]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: models.py SCHEMA string, conftest.py base fixtures
  - phase: 02-promptbuilder
    provides: async_db fixture pattern, prompt builder DB access pattern

provides:
  - conversation_turns CREATE TABLE IF NOT EXISTS in models.py SCHEMA
  - Additive ALTER TABLE migration for key_facts and named_entities in migrations.py
  - 15 NotImplementedError test stubs covering all Phase 3 requirements (PERS-02, PERS-03, CTX-01, CTX-02, CTX-03)
  - db pytest fixture in conftest.py with full schema + Phase 3 additive columns

affects: [03-02-history-cache, 03-03-token-budget, 03-04-summarization, 03-05-session-continuity]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Safe idempotent ALTER TABLE: try/except loop per column so re-runs never crash"
    - "SCHEMA-only table definition + separate ALTER TABLE migration for additive columns"
    - "conftest.py extend-not-overwrite: imports FULL_SCHEMA from models.py, runs additive ALTER TABLE in fixture"

key-files:
  created:
    - tests/test_context_budget.py
  modified:
    - app/storage/models.py
    - app/storage/migrations.py
    - tests/conftest.py

key-decisions:
  - "conversation_turns added to SCHEMA (CREATE TABLE IF NOT EXISTS) — idempotent by design"
  - "key_facts and named_entities added via ALTER TABLE in run_migrations(), not in SCHEMA — avoids schema drift for existing DBs"
  - "db fixture imports FULL_SCHEMA from app.storage.models (not a copy) so fixture always stays in sync with production schema"
  - "No db fixture collision with existing async_db — db is new name, no rename needed"

patterns-established:
  - "Additive migration pattern: for col in cols: try ALTER TABLE except pass"
  - "TDD Wave 0 scaffold: write stubs first, implement in later plans"

requirements-completed: [PERS-02, PERS-03]

# Metrics
duration: 5min
completed: 2026-03-28
---

# Phase 03 Plan 01: Context Budget Manager — Schema & Test Scaffold Summary

**SQLite conversation_turns table added to SCHEMA, key_facts/named_entities wired via safe ALTER TABLE migration, and 15 red pytest stubs scaffolded for all Phase 3 requirements**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-28T17:33:38Z
- **Completed:** 2026-03-28T17:38:45Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `conversation_turns` table (id, chat_id, role, content, created_at) to SCHEMA in models.py
- Extended migrations.py with safe try/except ALTER TABLE loop adding key_facts TEXT and named_entities TEXT to conversation_summaries without data loss
- Extended tests/conftest.py with `db` fixture using full SCHEMA + Phase 3 additive columns (extended, not overwritten)
- Created tests/test_context_budget.py with exactly 15 NotImplementedError stubs: all fail red, zero import errors

## Task Commits

Each task was committed atomically:

1. **Task 1: conversation_turns table + additive migration** - `6f45531` (feat)
2. **Task 2: Test scaffold — conftest.py extend + 15 stubs** - `85782c0` (test)

**Plan metadata:** (final docs commit — see below)

## Files Created/Modified

- `app/storage/models.py` - Appended conversation_turns CREATE TABLE IF NOT EXISTS to SCHEMA
- `app/storage/migrations.py` - Added additive ALTER TABLE loop for key_facts/named_entities before db.commit()
- `tests/conftest.py` - Extended with `db` async fixture importing FULL_SCHEMA from models.py
- `tests/test_context_budget.py` - New file: 15 NotImplementedError stubs covering PERS-02, PERS-03, CTX-01, CTX-02, CTX-03

## Decisions Made

- `key_facts` and `named_entities` are NOT in the SCHEMA string — they live in run_migrations() ALTER TABLE to avoid applying them to the CREATE TABLE statement that may already exist on production DBs. This keeps the SCHEMA as the authoritative table definition and ALTER TABLE as the safe additive path.
- The `db` fixture imports `FULL_SCHEMA` directly from `app.storage.models` so the fixture always stays in sync with the production schema — no copy-paste drift.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 15 test stubs are in place and fail red — Plan 03-02 can immediately begin implementing history cache logic against these stubs
- The `db` fixture provides an in-memory aiosqlite connection with full schema including conversation_turns and the Phase 3 columns, ready for all remaining plans to use
- No blockers

---
*Phase: 03-context-budget-manager*
*Completed: 2026-03-28*
