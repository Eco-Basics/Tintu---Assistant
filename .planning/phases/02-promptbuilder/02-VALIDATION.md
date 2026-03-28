---
phase: 2
slug: promptbuilder
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (installed in Phase 1) |
| **Config file** | pytest.ini (created in Phase 1 Wave 0) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | PERS-01 | unit | `pytest tests/test_prompt_builder.py -x -q` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | PERS-01 | unit | `pytest tests/test_prompt_builder.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 0 | PERS-04 | unit | `pytest tests/test_preference_echo.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02 | 1 | PERS-04 | unit | `pytest tests/test_preference_echo.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_prompt_builder.py` — stubs for PERS-01 (prompt assembly order, preferences included, traits placeholder, persona appended)
- [ ] `tests/test_preference_echo.py` — stubs for PERS-04 (natural language confirmation format)

*Phase 1 created tests/__init__.py, conftest.py, pytest.ini — these are already present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Assembled prompt visible in DEBUG log during live bot run | PERS-01 | Requires running bot with LOG_LEVEL=DEBUG | Start bot, send a message, grep logs for "system_prompt=" |
| Preference set in one session active after bot restart | PERS-01 | Requires two live sessions and process restart | Set preference, restart bot service, send answer-intent message, verify tone |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
