---
phase: 03-context-budget-manager
plan: 04
subsystem: memory
tags: [summarization, key_facts, sqlite, asyncio, telegram]

# Dependency graph
requires:
  - phase: 03-context-budget-manager plan 01
    provides: conversation_turns table, conversation_summaries.key_facts column via migration
  - phase: 03-context-budget-manager plan 02
    provides: write_conversation_turn(), history_cache, handlers.py turn-writing wiring

provides:
  - get_turn_count_since_last_summary(chat_id) in summarizer.py
  - generate_session_summary(chat_id) returning (summary_text, key_facts_text, row_id)
  - apply_key_facts_correction(summary_id, correction_text) updating key_facts column
  - KEY_FACTS_PROMPT for verbatim fact extraction
  - summarize_and_notify() background task in handlers.py
  - 20-turn trigger in handlers.py firing asyncio.create_task
  - _pending_corrections dict for cross-async correction detection
  - /summarize command handling in router.py with _run_summary() helper

affects:
  - 03-05-session-continuity (reads conversation_summaries.key_facts for resume context)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - asyncio.create_task for fire-and-forget background summarization
    - Module-level dict (_pending_corrections) for state across async boundaries
    - Mock-and-patch for summarizer unit tests (no real DB/LLM calls needed)

key-files:
  created: []
  modified:
    - app/memory/summarizer.py
    - app/bot/handlers.py
    - app/bot/router.py
    - tests/test_context_budget.py

key-decisions:
  - "_pending_corrections module-level dict used to bridge summarize_and_notify() result back to message_handler — context.user_data is inaccessible in background tasks"
  - "summarize intent branch placed before draft_reply in router.py to allow explicit /summarize command to short-circuit normal routing"
  - "generate_session_summary queries only turns since last summary (not all turns) to avoid re-summarizing already-compressed history"

patterns-established:
  - "Fire-and-forget pattern: asyncio.create_task() used for background summarization; errors logged but never surface to user"
  - "Correction detection: next user message after summary is treated as correction if pending_summary_id is present (checked before normal routing)"

requirements-completed: [PERS-03]

# Metrics
duration: 25min
completed: 2026-03-28
---

# Phase 03 Plan 04: Summarization Summary

**Session auto-summarization at 20 turns with key_facts extraction, Telegram delivery, and correction support via apply_key_facts_correction()**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-28T17:53:30Z
- **Completed:** 2026-03-28T18:18:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Extended summarizer.py with KEY_FACTS_PROMPT, get_turn_count_since_last_summary, generate_session_summary (populates key_facts column), and apply_key_facts_correction
- Wired 20-turn trigger into handlers.py with asyncio.create_task(summarize_and_notify), and added correction detection before normal routing
- Added /summarize command handling in router.py with fire-and-forget _run_summary() helper
- Replaced 4 NotImplementedError stubs with real assertions — all 4 green; overall suite 13 passed 2 failed (continuity stubs remain for Plan 03-05)

## Task Commits

1. **Task 1: Extend summarizer.py with key_facts and session summary functions** - `97fa6a7` (feat)
2. **Task 2: Wire trigger, /summarize command, 4 test stubs** - incorporated into `1b21225` (feat, 03-03 pre-wired handlers/router/tests)

## Files Created/Modified

- `app/memory/summarizer.py` - Added KEY_FACTS_PROMPT, get_turn_count_since_last_summary, generate_session_summary, apply_key_facts_correction; merged fetchall/fetchone into db import
- `app/bot/handlers.py` - Added SUMMARIZE_TRIGGER=20, _pending_corrections dict, summarize_and_notify() background task, 20-turn trigger, correction detection block
- `app/bot/router.py` - Added asyncio import, summarize intent branch (before draft_reply), _run_summary() helper
- `tests/test_context_budget.py` - Replaced 4 NotImplementedError stubs: test_summarize_fires_at_20_turns, test_summarize_command_triggers, test_summary_sent_to_user, test_keyfacts_correction_updates_db

## Decisions Made

- `_pending_corrections` module-level dict chosen to bridge summarize_and_notify() result back to message_handler — context.user_data is only accessible in synchronous handler scope, not inside background asyncio tasks.
- summarize intent branch placed before draft_reply so `/summarize` and `summarize` text messages are intercepted before the general answer path.
- generate_session_summary queries only turns created after the most recent summary's created_at timestamp, preventing re-summarization of already-compressed history.

## Deviations from Plan

None - plan executed exactly as written. Note: Plan 03-03 had pre-implemented the handlers.py and router.py wiring as part of its ContextBudgetManager integration work. The Task 2 edits confirmed that content was already in place and the 4 test stubs were the primary remaining work.

## Issues Encountered

- Task 1 summarizer.py import failed without env vars (TELEGRAM_TOKEN not set). Resolved by setting env vars for verification; this is expected — tests use conftest.py env stubs.
- Task 2 commit appeared to have no diff because Plan 03-03 had pre-populated handlers.py and router.py with the 03-04 wiring. Task 2 contribution was filling the 4 test stubs and confirming all wiring matched the plan spec.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- summarizer.py is complete and ready for Plan 03-05 which will add continuity signals (resume/fresh) to load_conversation_state()
- key_facts are stored in conversation_summaries and will be available for context injection in Plan 03-05
- 2 stubs remain red (test_continuity_signal_resume, test_continuity_signal_fresh) — these are Plan 03-05 targets

---
*Phase: 03-context-budget-manager*
*Completed: 2026-03-28*
