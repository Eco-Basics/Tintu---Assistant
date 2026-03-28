---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml (Wave 0 installs) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | FOUND-01 | unit | `pytest tests/test_refusal.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | FOUND-01 | unit | `pytest tests/test_refusal.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 0 | FOUND-02 | unit | `pytest tests/test_migrations.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | FOUND-02 | unit | `pytest tests/test_migrations.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_refusal.py` — stubs for FOUND-01 (refusal guard tests)
- [ ] `tests/test_migrations.py` — stubs for FOUND-02 (schema migration tests)
- [ ] `tests/conftest.py` — shared fixtures (bot mocks, DB setup)
- [ ] `pytest` added to requirements.txt

*No test infrastructure currently exists — Wave 0 must create it.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Refusal fires before Ollama call in live bot | FOUND-01 | Requires running Telegram bot + real message | Send code request via Telegram; confirm no Ollama call in logs |
| Both bots apply refusal independently | FOUND-01 | Requires two live bot processes | Restart each bot, send code request to each separately |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
