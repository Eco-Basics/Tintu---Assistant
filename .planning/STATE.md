---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Completed 03-context-budget-manager 03-02-PLAN.md
last_updated: "2026-03-28T17:50:21.998Z"
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 11
  completed_plans: 8
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Each user gets an assistant that genuinely adapts to them — remembering preferences, speaking in a shaped style, staying within honest capabilities.
**Current focus:** Phase 03 — context-budget-manager

## Current Position

Phase: 03 (context-budget-manager) — EXECUTING
Plan: 1 of 5

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01-foundation P01 | 10 | 2 tasks | 6 files |
| Phase 02-promptbuilder P03 | 2 | 1 tasks | 1 files |
| Phase 02-promptbuilder P01 | 15 | 2 tasks | 4 files |
| Phase 02-promptbuilder P04 | 5 | 3 tasks | 4 files |
| Phase 03-context-budget-manager P01 | 5 | 2 tasks | 4 files |
| Phase 03-context-budget-manager P02 | 11 | 2 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: 3 phases from 9 v1 requirements; capability refusal ships first to prevent hallucinated answers during personality testing
- Roadmap: Goal 2 (Claude CLI multi-session) is out of scope for this milestone — build after Goal 1 validated in real use
- Stack: tiktoken token counting decision deferred to Phase 3 planning — validate against Ollama prompt_eval_count in first integration test
- [Phase 01-foundation]: Monkeypatch target is app.bot.router.classify (imported name), not app.llm.classifier.classify — router uses from-import binding
- [Phase 01-foundation]: CAPABILITY_REFUSALS guard placed after draft_reply block, before build_answer — preserves all existing intent dispatch
- [Phase 01-foundation]: Test env stubs set via os.environ.setdefault in conftest.py so app.config imports don't raise KeyError during tests
- [Phase 01-foundation 01-02]: No behavior_preferences table — preferences table fulfills that role; Phase 2 PromptBuilder reads from preferences
- [Phase 01-foundation 01-02]: personality_traits.confidence REAL DEFAULT 1.0 added now to avoid ALTER TABLE when DIFF-02 ships
- [Phase 01-foundation 01-02]: personas.is_active single-active enforcement is application-layer only, not a DB constraint
- [Phase 02-promptbuilder]: Default system='' in compare_against_prior() preserves backward compatibility — existing callers with no system arg are unaffected
- [Phase 02-promptbuilder 02-02]: Patch target for fetchall mock is app.llm.prompt_builder.fetchall (from-import binding) — same lesson as Phase 1 router.py monkeypatching
- [Phase 02-promptbuilder 02-02]: async_db fixture uses aiosqlite.Row factory so row['key'] dict-style access works correctly in tests
- [Phase 02-promptbuilder]: test_prompt_builder.py uses direct import (not importorskip) because prompt_builder.py already existed from prior work
- [Phase 02-promptbuilder]: [02-01] pytest.ini extended with testpaths=tests for explicit discovery scope; conftest.py extended not overwritten per RISK note
- [Phase 02-promptbuilder]: Patch target for build_system_prompt mock is app.llm.response_builder.build_system_prompt (from-import binding) — same lesson as Phase 1 router.py monkeypatching
- [Phase 03-context-budget-manager]: key_facts and named_entities added via ALTER TABLE in run_migrations(), not in SCHEMA — avoids schema drift for existing DBs
- [Phase 03-context-budget-manager]: db fixture imports FULL_SCHEMA directly from app.storage.models so fixture stays in sync with production schema
- [Phase 03-context-budget-manager]: Turns written AFTER reply_text so user gets response even if DB write fails
- [Phase 03-context-budget-manager]: history_cache module singleton imported directly — consistent with execute/fetchall pattern in codebase
- [Phase 03-context-budget-manager]: [03-02] From-import patch target is app.llm.conversation_state.fetchall — same lesson as Phase 1 router.py monkeypatching

### Pending Todos

None yet.

### Blockers/Concerns

- Hetzner VPS not yet provisioned — code can be written and unit-tested locally first
- Friend's Telegram token/ID/timezone TBD — only affects assistant-friend deployment, not development

### Open Risks (MY MODE Pass 1 Audit — flagged 2026-03-28)

**Phase 1 risks:**

- **[RISK — Phase 1 execution]** pytest Python version compatibility unverified — confirm Python ≥ 3.8 before running `pip install pytest==7.4.4 pytest-asyncio==0.23.8`. Adjust version pins if needed.
- **[VERIFY — Phase 1 execution]** `build_retrieval_answer()` location assumed in router.py — confirm before monkeypatching in `test_retrieval_bypass`. If it lives in response_builder.py, patch target must change.
- **[VERIFY — Phase 1 execution]** Keyword patterns in CAPABILITY_REFUSALS must cover the most common hallucination triggers. Review during Phase 1 execution; expand if obvious requests slip through.
- **[VERIFY — Phase 1 execution]** classify() edge cases: messages like "remind me to look up how to code X" should route to set_reminder, not answer. Validate with real messages during Phase 1 UAT.
- **[RESOLVED — Phase 2 planning]** ~~preferences table (key/value/source) assumed compatible with Phase 2 PromptBuilder~~ — confirmed compatible in Phase 2 discuss-phase, no migration needed.

**Phase 2 risks:**

- **[VERIFY — Phase 2 execution]** `compare_against_prior()` in comparison.py does not currently accept a `system=` kwarg. Plan 02-03 adds it — read the existing signature in comparison.py before editing to avoid breaking the call site.
- **[RISK — Phase 2 execution]** Preference echo `f"Saved: I'll {source}."` — `source` may be NULL or noun-phrased. Add a NULL guard and review template phrasing during Phase 2 UAT.
- **[RISK — Phase 2 execution]** Plan 02-01 recreates pytest infrastructure (conftest.py, requirements.txt, tests/__init__.py) that Phase 1 already created. Read existing files first and extend/merge rather than overwrite.
- **[VERIFY — Phase 2 execution]** systemd service files may lack `Environment=LOG_LEVEL=DEBUG`. Check `systemd/assistant-mithu.service` and `systemd/assistant-friend.service` during Phase 2 UAT.

**Phase 3 risks:**

- **[RISK — Phase 3 execution]** Plans 03-03 and 03-04 are parallel (Wave 2) but both modify `app/bot/handlers.py`. Executor must serialize writes to that file — complete all handlers.py edits from one plan before starting the other's handlers.py changes.
- **[RISK — Phase 3 execution]** Async summarization has no error fallback — if Ollama is unreachable when the 20-turn trigger fires, the background task will silently fail and no summary will be stored. Acceptable for v1; log the error and continue without blocking the user response.

**Cross-phase risks (Pass 1.5 audit — 2026-03-28):**

- **[RISK — execution all phases]** `tests/conftest.py` is modified by Phase 1 Plan 01-01, Phase 2 Plan 02-01, and Phase 3 Plan 03-01. Each executor MUST read the current conftest.py before editing and extend/merge existing fixtures — never overwrite. Overwriting will break prior phase tests.
- **[VERIFY — Phase 3 execution]** `/summarize` command routing is added to router.py in Plan 03-04, but python-telegram-bot may also require a `CommandHandler` registration in `main.py` or `handlers.py`. Executor for Plan 03-04 must check whether `/summarize` needs explicit `app.add_handler(CommandHandler("summarize", ...))` registration and add it if so.

## Session Continuity

Last session: 2026-03-28T17:50:21.993Z
Stopped at: Completed 03-context-budget-manager 03-02-PLAN.md
Resume file: None
