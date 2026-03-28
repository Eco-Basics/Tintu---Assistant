---
phase: 02-promptbuilder
plan: 04
subsystem: llm-integration
tags: [prompt-builder, integration, wiring, pers-04, testing]
dependency_graph:
  requires: [02-02, 02-03]
  provides: [dynamic-system-prompt-active, pers-04-echo]
  affects: [app/llm/response_builder.py, app/bot/router.py]
tech_stack:
  added: []
  patterns: [from-import-mock-patching, async-mock-sentinel]
key_files:
  created:
    - tests/test_response_builder.py
  modified:
    - app/llm/response_builder.py
    - app/bot/router.py
    - tests/test_preference_echo.py
decisions:
  - "Patch target for build_system_prompt mock is app.llm.response_builder.build_system_prompt (from-import binding), not app.llm.prompt_builder.build_system_prompt — same from-import lesson as Phase 1 router.py"
  - "commands.py still uses static SYSTEM_PROMPT — out of scope for this plan; deferred as separate item"
metrics:
  duration: 5 minutes
  completed_date: "2026-03-28"
  tasks_completed: 3
  files_modified: 4
---

# Phase 02 Plan 04: Call-Site Wiring and PERS-04 Echo Summary

**One-liner:** Activated Phase 2 by wiring `build_system_prompt()` into all four user-visible Ollama call sites and replacing raw key/value preference confirmation with natural-language `"Saved: I'll {source}."` echo.

## What Was Built

This plan is the integration step that makes Phase 2 live. Before this plan, `build_system_prompt()` existed but was never called — every user response still used the static `SYSTEM_PROMPT` constant. After this plan, all four user-facing call sites dynamically assemble the system prompt from DB preferences, personality traits, and active persona.

### Changes Made

**app/llm/response_builder.py**
- Removed `from app.llm.prompts import SYSTEM_PROMPT`
- Added `from app.llm.prompt_builder import build_system_prompt`
- All three functions (`build_answer`, `build_retrieval_answer`, `build_compare_answer`) now call `system = await build_system_prompt()` before passing to `generate()` / `compare_against_prior()`

**app/bot/router.py**
- Removed `SYSTEM_PROMPT` from the prompts import block
- Added `from app.llm.prompt_builder import build_system_prompt`
- `draft_reply` block: calls `system = await build_system_prompt()` before `generate()`
- `update_preference` block: return changed from `f"Preference saved: *{key}* = {value}"` to `f"Saved: I'll {source.lower().rstrip('.')}."` (PERS-04)
- All extraction calls (`PREFERENCE_EXTRACT_PROMPT`, `TASK_EXTRACT_PROMPT`, etc.) unchanged — no `system=` arg added

**tests/test_preference_echo.py**
- Replaced `pytest.fail` stubs with real string assertions for the `"Saved: I'll {source}."` echo format

**tests/test_response_builder.py** (new)
- Mock-based test using `AsyncMock` and `patch` to verify `build_answer()` passes `build_system_prompt()`'s return value as the `system=` argument to `generate()`
- Patch target: `app.llm.response_builder.build_system_prompt` (from-import binding)

## Test Results

```
18 passed in 0.27s
```

All 18 tests green: 4 migration tests, 2 preference echo tests, 6 prompt builder tests, 5 refusal tests, 1 response builder wiring test.

## Decisions Made

1. **Patch target for mock:** `app.llm.response_builder.build_system_prompt` — since response_builder.py uses `from app.llm.prompt_builder import build_system_prompt`, the name is bound in response_builder's namespace. Patching at the definition site (`app.llm.prompt_builder.build_system_prompt`) would not intercept the already-imported reference. This is the same from-import lesson applied in Phase 1 and Phase 2 Plan 02.

2. **commands.py deferred:** `app/bot/commands.py` still uses `system=SYSTEM_PROMPT` in two places. This file was out of scope for this plan (not listed in `files_modified`). Noted as deferred item below.

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Items

- `app/bot/commands.py` lines 329, 342: still use `system=SYSTEM_PROMPT`. These call sites are outside the plan scope. Should be wired in a follow-up task when commands.py is within scope.

## Self-Check: PASSED

All key files found on disk:
- app/llm/response_builder.py: FOUND
- app/bot/router.py: FOUND
- tests/test_preference_echo.py: FOUND
- tests/test_response_builder.py: FOUND
- .planning/phases/02-promptbuilder/02-04-SUMMARY.md: FOUND

All task commits found:
- 761207c (Task 1 — response_builder wiring): FOUND
- a98de30 (Task 2 — router.py + PERS-04 echo): FOUND
- 42900a9 (Task 3 — test_response_builder mock test): FOUND
