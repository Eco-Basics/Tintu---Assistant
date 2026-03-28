---
phase: 02-promptbuilder
plan: 03
subsystem: memory
tags: [ollama, async, python, comparison, system-prompt]

# Dependency graph
requires:
  - phase: 02-promptbuilder
    provides: ollama_client.generate() with system kwarg (confirmed in Plan 02-01 context)
provides:
  - compare_against_prior() accepts system: str = "" and threads it to generate()
affects: [02-04-promptbuilder, plan-04-build-compare-answer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thread-through pattern: add default='' param, pass as kwarg to inner async call"

key-files:
  created: []
  modified:
    - app/memory/comparison.py

key-decisions:
  - "Default system='' preserves backward compatibility — existing callers with no system arg are unaffected"

patterns-established:
  - "System prompt thread-through: functions that delegate to generate() should accept system kwarg with default empty string"

requirements-completed: [PERS-01]

# Metrics
duration: 2min
completed: 2026-03-28
---

# Phase 02 Plan 03: System Parameter Thread-Through in compare_against_prior() Summary

**compare_against_prior() extended with system: str = "" kwarg that passes through to generate(), enabling Plan 04 to inject dynamic system prompts into comparison calls**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-28T16:40:26Z
- **Completed:** 2026-03-28T16:42:40Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added `system: str = ""` parameter to `compare_against_prior()` with a default that keeps all existing callers working unchanged
- Threaded the parameter through to `await generate(prompt, system=system)` — the gap identified as Pitfall 1 in Phase 2 research
- Full test suite (9 tests) passes with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add system parameter to compare_against_prior()** - `057fb7e` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `app/memory/comparison.py` - Added `system: str = ""` param to function signature, pass through to `generate()`

## Decisions Made
- None — followed plan as specified. The two-line change was exactly as described in the plan.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
- `python -c "from app.memory.comparison import compare_against_prior"` fails without env vars because `app.config` raises `KeyError: 'TELEGRAM_TOKEN'` at import time. This is a pre-existing requirement (present before this plan). Verified with env vars stubbed: import succeeds cleanly. Not a regression.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- `compare_against_prior()` is ready for Plan 04 (`build_compare_answer()`) to call it with a dynamic system prompt
- No blockers — the gap (Pitfall 1) is resolved

---
*Phase: 02-promptbuilder*
*Completed: 2026-03-28*
