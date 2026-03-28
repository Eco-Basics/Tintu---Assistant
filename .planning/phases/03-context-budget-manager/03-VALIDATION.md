---
phase: 3
slug: context-budget-manager
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4.4 + pytest-asyncio 0.23.8 |
| **Config file** | `pytest.ini` (created in Phase 1 Wave 0) |
| **Quick run command** | `pytest tests/test_context_budget.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~5–10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_context_budget.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | PERS-02 | unit | `pytest tests/test_context_budget.py::test_conversation_turns_table -x -q` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 0 | PERS-03 | unit | `pytest tests/test_context_budget.py::test_conversation_summaries_columns -x -q` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | PERS-02 | unit | `pytest tests/test_context_budget.py::test_history_append_and_cap -x -q` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 1 | PERS-02 | unit | `pytest tests/test_context_budget.py::test_history_prepend_format -x -q` | ❌ W0 | ⬜ pending |
| 3-02-03 | 02 | 1 | PERS-02 | unit | `pytest tests/test_context_budget.py::test_extraction_calls_no_history -x -q` | ❌ W0 | ⬜ pending |
| 3-02-04 | 02 | 1 | PERS-02 | unit | `pytest tests/test_context_budget.py::test_reload_on_startup -x -q` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 2 | CTX-01 | unit | `pytest tests/test_context_budget.py::test_token_budget_under_8192 -x -q` | ❌ W0 | ⬜ pending |
| 3-03-02 | 03 | 2 | CTX-01 | unit | `pytest tests/test_context_budget.py::test_history_trim_oldest_first -x -q` | ❌ W0 | ⬜ pending |
| 3-03-03 | 03 | 2 | CTX-02 | unit | `pytest tests/test_context_budget.py::test_active_tasks_injected -x -q` | ❌ W0 | ⬜ pending |
| 3-04-01 | 04 | 3 | PERS-03 | unit | `pytest tests/test_context_budget.py::test_summarize_fires_at_20_turns -x -q` | ❌ W0 | ⬜ pending |
| 3-04-02 | 04 | 3 | PERS-03 | unit | `pytest tests/test_context_budget.py::test_summarize_command_triggers -x -q` | ❌ W0 | ⬜ pending |
| 3-04-03 | 04 | 3 | PERS-03 | unit | `pytest tests/test_context_budget.py::test_summary_sent_to_user -x -q` | ❌ W0 | ⬜ pending |
| 3-04-04 | 04 | 3 | PERS-03 | unit | `pytest tests/test_context_budget.py::test_keyfacts_correction_updates_db -x -q` | ❌ W0 | ⬜ pending |
| 3-05-01 | 05 | 4 | CTX-03 | unit | `pytest tests/test_context_budget.py::test_continuity_signal_resume -x -q` | ❌ W0 | ⬜ pending |
| 3-05-02 | 05 | 4 | CTX-03 | unit | `pytest tests/test_context_budget.py::test_continuity_signal_fresh -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_context_budget.py` — stubs for PERS-02, PERS-03, CTX-01, CTX-02, CTX-03
- [ ] `tests/conftest.py` — extend with async DB fixture for conversation_turns + conversation_summaries (Phase 1/2 conftest.py already exists — extend, do not overwrite)
- [ ] `pytest.ini` already exists from Phase 1 — no reinstall needed

*Phase 1 already installed pytest + pytest-asyncio. Wave 0 extends existing infrastructure.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Summarization fires async and user receives the Telegram summary message | PERS-03 | Requires live Telegram bot + real Ollama call | Send 20 test messages; verify summary arrives as a separate Telegram message after the 20th response |
| Token count validated against Ollama's prompt_eval_count | CTX-01 | Requires live Ollama call | Enable DEBUG logging; send a long message with 8 turns of history; compare logged token_estimate vs prompt_eval_count in Ollama response |
| Continuity signal shown on first message after bot restart | CTX-03 | Requires live bot restart | Restart service; send first message; verify signal appears in response |
| /summarize command triggers summary and sends it to user | PERS-03 | Requires live Telegram bot | Send /summarize; verify bot responds with summary and it's stored in conversation_summaries |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
