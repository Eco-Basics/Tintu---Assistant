---
phase: 02-promptbuilder
plan: 02
subsystem: llm
tags: [aiosqlite, pytest, asyncio, mocking, system-prompt, pers-01]

# Dependency graph
requires:
  - phase: 02-promptbuilder/02-01
    provides: conftest.py in_memory_db fixture, pytest infrastructure, LOG_LEVEL env support
  - phase: 01-foundation/01-02
    provides: personality_traits and personas tables in DB schema (models.py SCHEMA)

provides:
  - app/llm/prompt_builder.py with async build_system_prompt() function
  - Layered prompt assembly: SYSTEM_PROMPT + behavior preferences + personality traits + active persona
  - DEBUG log of assembled prompt on every call (PERS-01 observability)
  - tests/test_prompt_builder.py with 6 green tests covering all PERS-01 behaviors
  - async_db fixture in conftest.py (in-memory SQLite with all three tables)

affects:
  - 02-03 (compare_against_prior uses build_system_prompt via system= kwarg)
  - 02-04 (router.py wires update_preference, which feeds preferences table read by this function)
  - All future Ollama calls that replace static SYSTEM_PROMPT with build_system_prompt()

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Patch from-import bindings at the usage site: patch('app.llm.prompt_builder.fetchall'), not 'app.storage.db.fetchall'"
    - "Sections joined with double newlines; each section is self-contained string"
    - "fetchall() called three times per invocation: preferences, personality_traits, personas"

key-files:
  created:
    - app/llm/prompt_builder.py
    - tests/test_prompt_builder.py
  modified:
    - tests/conftest.py

key-decisions:
  - "Patch target for mocking fetchall is app.llm.prompt_builder.fetchall (from-import binding), not app.storage.db.fetchall — same pattern as Phase 1 router.py monkeypatching lesson"
  - "async_db fixture added to conftest.py alongside in_memory_db (not replaced) — extends Phase 1 infrastructure"

patterns-established:
  - "Prompt assembly pattern: sections list built with conditionals, joined with double newlines"
  - "fetchall mock uses side_effect list for sequential return values across multiple calls in one function"

requirements-completed: [PERS-01]

# Metrics
duration: 24min
completed: 2026-03-28
---

# Phase 02 Plan 02: build_system_prompt Implementation Summary

**Async build_system_prompt() assembles layered system prompt from three SQLite tables with DEBUG logging on every Ollama call**

## Performance

- **Duration:** 24 min
- **Started:** 2026-03-28T16:41:56Z
- **Completed:** 2026-03-28T17:06:26Z
- **Tasks:** 1 TDD task (RED + GREEN phases)
- **Files modified:** 3

## Accomplishments
- Created `app/llm/prompt_builder.py` with `async build_system_prompt() -> str`
- Implements locked section order: SYSTEM_PROMPT → behavior preferences → personality traits → active persona
- Emits `logger.debug(f"system_prompt=\n{assembled}")` on every call for PERS-01 observability
- 6 unit tests cover all behaviors (empty tables, preferences section, traits placeholder, active persona, inactive persona exclusion, debug log)
- Extended conftest.py with `async_db` fixture providing all three tables in-memory

## Task Commits

TDD plan (RED then GREEN):

1. **RED phase: failing tests** - `95a9a23` (test)
2. **GREEN phase: implementation** - `ddffc14` (feat)

## Files Created/Modified
- `app/llm/prompt_builder.py` — new module, exports `build_system_prompt()` async function
- `tests/test_prompt_builder.py` — 6 green tests for all PERS-01 behaviors
- `tests/conftest.py` — extended with `async_db` fixture (preferences, personality_traits, personas tables)

## Decisions Made
- Patch target for fetchall mock is `app.llm.prompt_builder.fetchall` (the from-import binding), not `app.storage.db.fetchall`. Using the wrong target caused all 6 tests to fail with `RuntimeError: threads can only be started once` because the real aiosqlite `get_db()` was called instead of the mock.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed mock patch target in tests**
- **Found during:** GREEN phase (first test run)
- **Issue:** Tests patched `app.storage.db.fetchall` but `prompt_builder.py` uses a from-import binding (`from app.storage.db import fetchall`), so the mock didn't intercept calls — the real DB connection was hit instead, causing `RuntimeError: threads can only be started once`
- **Fix:** Changed all 6 test patches from `app.storage.db.fetchall` to `app.llm.prompt_builder.fetchall`
- **Files modified:** tests/test_prompt_builder.py
- **Verification:** All 6 tests passed after fix
- **Committed in:** ddffc14 (GREEN phase commit)

**2. [Rule 3 - Blocking] Added async_db fixture missing from conftest.py (prerequisite from 02-01)**
- **Found during:** Pre-execution check
- **Issue:** Plan 02-01 was partially executed — `async_db` fixture and `tests/test_prompt_builder.py` were not created, which are prerequisites for this TDD plan
- **Fix:** Added `async_db` fixture to conftest.py (with FIXTURE_SCHEMA creating all three tables), created initial test stub file
- **Files modified:** tests/conftest.py
- **Committed in:** 95a9a23 (RED phase commit)

---

**Total deviations:** 2 auto-fixed (1 blocking prerequisite, 1 blocking test bug)
**Impact on plan:** Both fixes necessary to make tests run. No scope creep.

## Issues Encountered
- Plan 02-01 SUMMARY.md was never created and `async_db` fixture was missing from conftest.py. The partial 02-01 work (requirements.txt, logging.py) was already committed but the test scaffold was not. Handled as blocking deviation.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `build_system_prompt()` is ready for Plan 02-03 integration (compare_against_prior system= kwarg)
- Plan 02-04 will wire router.py to call `build_system_prompt()` on every Ollama call and handle `update_preference` echo
- Preferences table is read by this function — any row inserted by Plan 02-04 will appear in prompts immediately

---
*Phase: 02-promptbuilder*
*Completed: 2026-03-28*
