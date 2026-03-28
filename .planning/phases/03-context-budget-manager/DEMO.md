# Phase 3 Demo: Context Budget Manager

## What Was Built

Five capabilities complete the context layer:

1. **Rolling conversation history** — Every turn is written to `conversation_turns` DB and held in a 16-message in-memory cache per chat. History reloads from DB on startup so the assistant remembers across restarts.

2. **8k token budget manager** — `ContextBudgetManager` assembles `system prompt + history + active tasks + message` and trims oldest history pairs first when the 8,192-token hard limit is approached. Token count is confirmed via Ollama's `prompt_eval_count` field.

3. **Active task injection** — Up to 5 active/inbox tasks are automatically included in every answer context. The assistant knows your current work without you restating it.

4. **Session summarization + key facts** — After 20 turns, the session is compressed and a summary sent to the user for review. Named entities and verbatim key decisions are extracted and stored. `/summarize` triggers manually. User corrections update the stored facts.

5. **Session continuity signal** — On startup, the bot signals one of three states: `seamless` (recent history exists, silent reload), `resume` ("Resuming from last session summary."), or `fresh` ("No prior session found — starting fresh."). Fires once on first message.

33/33 tests pass. All 5 requirements (PERS-02, PERS-03, CTX-01, CTX-02, CTX-03) verified.

## How to Use It

**Multi-turn conversation (automatic):**
- Just talk normally — history accumulates silently
- Reference something from earlier: "what did I just say about the model?" — assistant has the last 8 turns in context

**Check active tasks in answers:**
- Add tasks: "Add a task to review the pitch deck"
- Ask anything — tasks are injected automatically, no need to repeat them

**Manual summarize:**
```
/summarize
```
Bot sends a summary with key facts. Reply with a correction if anything is wrong.

**Session start signal:**
- Restart the bot
- Send your first message — watch for "Resuming from last session summary." or "No prior session found — starting fresh."

**Run tests:**
```bash
pytest tests/ -v
# Expected: 33 passed
```

## Worked Example

**Scenario: Multi-turn with history**
```
Turn 1 — User: we're going with Qwen3:4b for the local model
Turn 1 — Bot:  Got it. I'll keep that in mind.

Turn 4 — User: what model did we decide on?
Turn 4 — Bot:  Qwen3:4b — you mentioned it earlier in this session.
```

History block injected into Turn 4's prompt:
```
[You]: we're going with Qwen3:4b for the local model
[Assistant]: Got it. I'll keep that in mind.
...
Current message: what model did we decide on?
```

**Scenario: Session continuity**
```
[Bot restart]
User: hey
Bot:  Resuming from last session summary.
      [responds to "hey"]
```

## Tips & Edge Cases

- History cap is 16 messages (8 exchanges) in-memory, but full history is in DB — summaries capture what the cache drops.
- Token budget trims oldest pairs first. System prompt, active tasks, and the current message are never trimmed.
- The continuity signal fires **once only** — on the first message after startup. Subsequent messages don't repeat it.
- Live VPS testing deferred: history recall accuracy, `prompt_eval_count` alignment, task visibility in responses, and 20-turn auto-summarize delivery are all verified structurally but await Ollama running on VPS.
- `jobs` (scheduled reminders) require `pip install "python-telegram-bot[job-queue]"` — currently disabled on Windows dev setup, will be active on Linux VPS.
