---
phase: 03-context-budget-manager
plan: 02
subsystem: database
tags: [sqlite, aiosqlite, conversation-cache, in-memory, handlers, history]

# Dependency graph
requires:
  - phase: 03-context-budget-manager
    plan: 01
    provides: conversation_turns table in SCHEMA, db fixture in conftest.py, 15 test stubs
  - phase: 01-foundation
    provides: handlers.py structure, main.py post_init pattern, db.py execute/fetchall

provides:
  - app/llm/conversation_state.py — ConversationCache class, history_cache singleton, write_conversation_turn(), load_conversation_state()
  - handlers.py — writes user+assistant turns to DB and in-memory cache after every route() response
  - main.py — calls load_conversation_state(TELEGRAM_USER_ID) in post_init before "Assistant ready."
  - 4 green tests: test_conversation_turns_table, test_conversation_summaries_columns, test_history_append_and_cap, test_reload_on_startup

affects: [03-03-token-budget, 03-04-summarization, 03-05-session-continuity]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module singleton: history_cache = ConversationCache() at module level — shared by handlers and context manager"
    - "Write-after-reply: persist turns after reply_text so response is delivered even if DB write fails"
    - "Mock-based test: patch fetchall at from-import binding (app.llm.conversation_state.fetchall)"

key-files:
  created:
    - app/llm/conversation_state.py
  modified:
    - app/bot/handlers.py
    - app/main.py
    - tests/test_context_budget.py

key-decisions:
  - "Turns written AFTER reply_text — user gets response even if DB is slow/unavailable"
  - "history_cache module singleton imported directly (not passed) — same pattern as db.py execute/fetchall"
  - "write_conversation_turn uses datetime('now') in SQL (not Python) for consistency with existing tables"
  - "load_conversation_state uses subquery + ORDER BY ASC to get last N rows in chronological order from DESC-ordered DB fetch"

patterns-established:
  - "From-import patch target: patch app.llm.conversation_state.fetchall not app.storage.db.fetchall (same lesson as Phase 1 router.py)"

requirements-completed: [PERS-02]

# Metrics
duration: 11min
completed: 2026-03-28
---

# Phase 03 Plan 02: History Cache Summary

**ConversationCache in-memory dict (16-message cap per chat_id) backed by conversation_turns DB writes on every exchange and startup reload from DB**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-28T17:35:24Z
- **Completed:** 2026-03-28T17:46:19Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created app/llm/conversation_state.py with ConversationCache class (append/get/set/clear), history_cache module singleton, write_conversation_turn() async DB insert, and load_conversation_state() async DB reload
- Wired handlers.py to write both user and assistant turns to DB and cache after every reply_text
- Extended main.py post_init to call load_conversation_state(TELEGRAM_USER_ID) before "Assistant ready." log
- 4 of 15 test stubs replaced with green assertions; 11 remaining stubs still fail red as expected

## Task Commits

Each task was committed atomically:

1. **Task 1: Create app/llm/conversation_state.py** - `b11db09` (feat)
2. **Task 2: Wire handlers.py + main.py + fill 4 test stubs** - `e5c1bab` (feat)

## Files Created/Modified

- `app/llm/conversation_state.py` - ConversationCache class, history_cache singleton, write_conversation_turn(), load_conversation_state()
- `app/bot/handlers.py` - Added import + turn writes after reply_text
- `app/main.py` - Added import + load_conversation_state call in post_init
- `tests/test_context_budget.py` - Replaced 4 stubs with green assertions

## Decisions Made

- Turns are written AFTER reply_text (not before) so the user always gets a response even if the DB write fails
- history_cache is a module-level singleton imported directly, consistent with how execute/fetchall are used throughout the codebase
- write_conversation_turn uses datetime('now') in the SQL string for consistency with all other tables
- load_conversation_state uses a DESC-then-ASC subquery pattern to get the last 16 rows in chronological order

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The verify command in the plan runs without TELEGRAM_TOKEN env var set, causing KeyError from app.config. Added env stubs (TELEGRAM_TOKEN=test TELEGRAM_USER_ID=0) to the manual check — no change to code needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- history_cache singleton ready for Plan 03-03 (token budget) to read and trim history before Ollama call
- write_conversation_turn() and load_conversation_state() available for Plans 03-03 through 03-05
- 11 test stubs remain red, ready for Plans 03-03 through 03-05 to fill in
- No blockers

---
*Phase: 03-context-budget-manager*
*Completed: 2026-03-28*
