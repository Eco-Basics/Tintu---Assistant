# Phase 1 Demo: Foundation

## What Was Built

Two foundational capabilities now protect users and prepare the data layer:

1. **Capability Refusal Guard** — The bot detects code, math, and research requests _before_ calling Ollama, and returns a clear refusal message instead of a hallucinated answer. Bypass logic preserves normal flow for reminders and retrieval intents.

2. **Personality Schema Migration** — Two new SQLite tables (`personality_traits`, `personas`) have been added to the database alongside the existing `preferences` table. Migrations are additive and idempotent — no existing data is ever lost on restart.

9/9 automated tests pass. Both requirements (FOUND-01, FOUND-02) are verified.

## How to Use It

**Capability Refusal (user-facing):**
1. Send the bot a message like "write me a Python function" or "solve 2x + 5 = 11"
2. The bot replies with a refusal message — no Ollama call is made
3. Normal messages (set a reminder, what's my task list) are unaffected and routed as usual

**Schema Migration (developer-facing):**
1. Start the bot normally — `python -m app.main` (or your service command)
2. The `personality_traits` and `personas` tables are created on first run if they don't exist
3. Re-running never drops or corrupts existing rows — safe to restart freely

**Running tests:**
```bash
pytest tests/ -v
# Expected: 9 passed in ~0.5s
```

## Worked Example

**Scenario: User asks the bot to write code**

Before Phase 1 — the bot would call Ollama and return hallucinated Python.

After Phase 1:
```
User: write a function to reverse a string in Python
Bot:  Sorry, I can't help with coding, math, or research questions. I'm here
      for reminders, tasks, and personal organisation.
```
Ollama is never called. The guard fires inside `route()` at lines 239–243 of `router.py`.

**Scenario: Set a reminder (should still work)**
```
User: remind me to call Mum at 6pm
Bot:  Done! I'll remind you to call Mum at 6 PM today.
```
The `set_reminder` intent bypasses the refusal check — only `intent == "answer"` is guarded.

## Tips & Edge Cases

- The refusal check is keyword-based (regex), not intent-based — even if the classifier misclassifies a code request as "answer", the guard catches it via the message text.
- The `preferences` table is **not** renamed to `behavior_preferences` — Phase 2 PromptBuilder reads from `preferences` directly.
- `personality_traits.confidence` column is already present (REAL DEFAULT 1.0) to avoid a future ALTER TABLE migration when adaptive confidence gating ships.
- On Windows Python 3.13, `zoneinfo` requires the `tzdata` package. Tests mock `today_str` to avoid this — production runs on Linux VPS where system tzdata is available.
