---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Completed 02-promptbuilder 02-02-PLAN.md (SUMMARY retroactively created)
last_updated: "2026-03-28T17:08:55.186Z"
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 11
  completed_plans: 5
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Each user gets an assistant that genuinely adapts to them — remembering preferences, speaking in a shaped style, staying within honest capabilities.
**Current focus:** Phase 02 — promptbuilder

## Current Position

Phase: 02 (promptbuilder) — EXECUTING
Plan: 2 of 4

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

Last session: 2026-03-28T17:06:26.000Z
Stopped at: Completed 02-promptbuilder 02-02-PLAN.md (SUMMARY retroactively created)
Resume file: None
