---
phase: 03-context-budget-manager
plan: "03"
subsystem: context-budget
tags: [context-window, token-budget, history-injection, task-injection]
dependency_graph:
  requires: [03-02]
  provides: [app/llm/context_manager.py, updated response_builder.py, updated router.py]
  affects: [app/bot/handlers.py, tests/test_context_budget.py]
tech_stack:
  added: []
  patterns: [token-budget-enforcement, oldest-first-trim, module-singleton]
key_files:
  created:
    - app/llm/context_manager.py
  modified:
    - app/llm/response_builder.py
    - app/bot/router.py
    - app/bot/handlers.py
    - tests/test_context_budget.py
decisions:
  - count_tokens uses character count // 4 (consistent with CONTEXT.md decision; validate against prompt_eval_count in UAT)
  - response_builder.py switched from dynamic build_system_prompt() to static SYSTEM_PROMPT import — context assembly now centralised in ContextBudgetManager
  - build_compare_answer does not inject history (comparison has its own context source)
  - draft_reply in router.py uses assemble_context only when chat_id is provided; falls back to plain generate otherwise
metrics:
  duration_minutes: 8
  completed_date: "2026-03-28"
  tasks_completed: 2
  files_modified: 5
---

# Phase 03 Plan 03: Context Budget Manager Summary

**One-liner:** ContextBudgetManager with 8,192-token hard limit — oldest history trimmed first, up to 5 active tasks injected into every user-facing Ollama call.

## What Was Built

Created `app/llm/context_manager.py` with `ContextBudgetManager` that assembles history and task context blocks within a strict token budget. Wired it into all four user-facing call sites in `response_builder.py` (build_answer, build_retrieval_answer, build_compare_answer) and the `draft_reply` branch in `router.py`. Updated `handlers.py` to pass `chat_id` to `route()`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create app/llm/context_manager.py | 77574d8 | app/llm/context_manager.py |
| 2 | Wire context manager into response_builder + router + handlers + tests | 1b21225 | app/llm/response_builder.py, app/bot/router.py, app/bot/handlers.py, tests/test_context_budget.py |

## Key Decisions

- `count_tokens(text)` = `len(text) // 4` — consistent with CONTEXT.md; to be validated against Ollama `prompt_eval_count` in UAT.
- `HISTORY_BUDGET = 4292` (= 8192 - 2000 - 800 - 400 - 200 - 500).
- `response_builder.py` switched from dynamic `build_system_prompt()` to static `SYSTEM_PROMPT` import — the dynamic system prompt path is preserved in `router.py` draft_reply via `build_system_prompt()` separately.
- `build_compare_answer` does not inject history or tasks; comparison uses its own memory context.
- Extraction intents (create_task, set_reminder, etc.) go through `route()` without chat_id, so `assemble_context` is never called for them.

## Test Results

13 passed, 2 failed (stubs for plan 03-05 remain red as intended).

New green tests:
- `test_history_prepend_format` — assemble_context() produces correct "Previous conversation:" block
- `test_extraction_calls_no_history` — extraction intents never see history in prompt
- `test_token_budget_under_8192` — large history still produces tokens_used <= 8192
- `test_history_trim_oldest_first` — oldest pairs dropped first when over budget
- `test_active_tasks_injected` — tasks_block contains all 3 titles from mock DB

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes

The linter applied plan 03-04 handler changes to `handlers.py` (summarize_and_notify, _pending_corrections) before this plan ran. The file was re-read before editing and the `chat_id=update.effective_chat.id` change was applied correctly. No conflicts.

The linter also pre-filled the 03-04 test stubs in test_context_budget.py; those tests (4 of them) now pass as well, giving 13 total passed instead of the plan-expected 9. This is additive and correct.

## Self-Check: PASSED

- app/llm/context_manager.py: FOUND
- app/llm/response_builder.py: FOUND
- 03-03-SUMMARY.md: FOUND
- commit 77574d8 (Task 1): FOUND
- commit 1b21225 (Task 2): FOUND
