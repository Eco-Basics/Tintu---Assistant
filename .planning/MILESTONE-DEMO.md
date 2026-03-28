# Milestone Demo: Tintu — Adaptive Personality Layer (v1.0)

## Overview

Tintu is a personal assistant running Qwen3:4b on your own server. Small models
are naturally honest about what they don't know — but they confidently hallucinate
code, math, and external facts. This milestone solves that and adds the full
personality layer: Tintu now refuses what it can't do, adapts its tone to your
preferences, remembers your conversations, and signals clearly when it's starting
fresh.

Three phases delivered this in order of trust: first make the bot honest (Phase 1),
then make it personal (Phase 2), then make it remember (Phase 3).

---

## Feature Inventory

### Phase 1: Foundation
**Contribution:** Prevents hallucinated answers before any personality work begins. Without this, stored preferences would just make Tintu sound more confident while still being wrong.

**Primary capability:** Any message asking for code, math, or research is intercepted in `router.py` before Ollama is called. The user receives a clear one-sentence refusal instead.

**Connects to:** Phase 2 (database tables for personality_traits and personas are created here, empty, ready for Phase 2 to populate).

### Phase 2: PromptBuilder
**Contribution:** Makes stored personality visible in every answer. Without this, preferences saved to the DB would never affect what the bot says.

**Primary capability:** Every Ollama call now receives a dynamically assembled system prompt built from the user's `preferences`, `personality_traits`, and active `personas`. Setting "be more direct" changes how every subsequent answer sounds. Preference saves echo back in natural language.

**Connects to:** Phase 1 (reads the tables Phase 1 created) → Phase 3 (Phase 3's ContextBudgetManager wraps this prompt into the full assembled context).

### Phase 3: Context Budget Manager
**Contribution:** Gives Tintu memory. Without this, every message is context-free — the bot can't reference what was said two turns ago and forgets everything on restart.

**Primary capability:** Rolling conversation history (16 turns in memory, full history in DB), 8k token budget enforcement with oldest-first trimming, active task injection into every answer, session summarization at 20 turns with key-fact extraction, and a session continuity signal on startup.

**Connects to:** Phase 2 (ContextBudgetManager passes the system prompt from PromptBuilder through to Ollama alongside history and tasks).

---

## End-to-End User Journey

You open Telegram and send your first message of the day.

**Session start:** Tintu replies to your first message with a signal — "Resuming from last session summary." if it has context from before, or "No prior session found — starting fresh." if this is the first time. You always know where you stand.

**Honest refusals:** You ask "can you write a regex for me?" — Tintu replies "I can't write or debug code — that's outside what I can do reliably." No Ollama call is made. No wrong output reaches you.

**Task and reminder management:** "Add a task to finish the client proposal" is captured and stored. "What's on my list?" returns your open items. "Remind me Friday at 5pm to send the invoice" is parsed and scheduled. These work regardless of whether Ollama is reachable.

**Personality in action:** You told Tintu last week "be more concise with me." Every answer since then — including this session after a restart — uses a system prompt that includes that preference. It doesn't ask you again.

**Memory across turns:** Four messages ago you mentioned "we're going with Supabase for the database." You ask "what was that DB decision?" — Tintu has it in rolling history and answers accurately without you repeating it.

**Active tasks in context:** You have three open tasks. When Tintu answers a question about your project, it's aware of those tasks and can connect them to what you're asking — without you listing them.

**Auto-summarize at 20 turns:** After a long session, Tintu sends you a separate message: "Session Summary: [summary]. Key facts captured: [facts]. If anything is wrong, reply with a correction." You reply "actually the deadline is Thursday not Friday" — Tintu updates the stored key fact.

**End of session:** You type "end of day review" or `/summarize` — Tintu compresses the session, extracts facts verbatim, and stores them. Next session starts with "Resuming from last session summary."

---

## Capability Showcase

### Capability Refusal Guard
**What it does:** Blocks code, math, and research requests before any Ollama call.

**How to use it:** Just send a request — "write a Python function", "solve 2x+5=11", "what's the latest AI news". The guard fires automatically.

**Good output looks like:**
```
User: write me a sorting algorithm
Bot:  I can't write or debug code — that's outside what I can do reliably.
```

**Common mistake:** Thinking the guard is intent-based only. It's also keyword-based — so even a misclassified message is caught by the regex patterns in `CAPABILITY_REFUSALS`.

---

### Dynamic Personality (PromptBuilder)
**What it does:** Assembles preferences + personality traits + active persona into the Ollama system prompt on every request.

**How to use it:**
1. Say "be more direct with me" or "I prefer bullet points"
2. Bot confirms: "Saved: I'll be more direct with you."
3. Every subsequent answer uses that preference — no restart needed

**Good output looks like:**
```
User: be more concise
Bot:  Saved: I'll be more concise.
[All future answers are noticeably shorter]
```

**Common mistake:** Expecting preferences from `commands.py` command handlers to use the dynamic prompt — those still use the static `SYSTEM_PROMPT`. Only natural-language conversation paths are wired to PromptBuilder.

---

### Rolling Conversation History
**What it does:** Keeps the last 8 exchanges (16 messages) in memory per session, persisted to DB across restarts.

**How to use it:** Just talk normally — history accumulates silently. Reference earlier context and the assistant uses it.

**Good output looks like:**
```
Turn 2: "We're using Fly.io for hosting"
Turn 6: "Where are we hosting this?"
Bot:    "Fly.io — you mentioned it a few turns ago."
```

**Common mistake:** Expecting unlimited history. The in-memory cache holds 16 messages; older turns are in DB and available via summarization, not live context.

---

### 8k Token Budget Manager
**What it does:** Hard-caps the assembled context (system prompt + history + tasks + message) at 8,192 tokens. Trims oldest history pairs first.

**How to use it:** Automatic — no configuration needed. Check `LOG_LEVEL=DEBUG` logs for `Context assembled chat_id=...` showing `tokens_used`.

**Good output looks like:**
```
[DEBUG] Context assembled chat_id=7912940724 tokens_used=3847/8192
```

**Common mistake:** Assuming the system prompt or current message could be trimmed — they never are. Only history is trimmed, oldest first.

---

### Session Summarization + Key Facts
**What it does:** After 20 turns, compresses the session and extracts verbatim named entities and decisions. Sends the summary to the user for review. Supports corrections.

**How to use it:**
- Automatic: fires after turn 20
- Manual: send `/summarize`
- Correct a fact: reply to the summary with the correction

**Good output looks like:**
```
Bot:  Session Summary (last 20 turns):
      [narrative summary]

      Key facts captured:
      - Decided on Qwen3:4b for local model
      - Hosting on Fly.io
      - Deadline is 2026-04-15

      If anything is wrong, reply with a correction and I'll update the record.
```

**Common mistake:** Sending a correction immediately after an unrelated message — the correction detection window is only active right after the summary is sent.

---

### Session Continuity Signal
**What it does:** Tells you on first message whether the assistant has prior context.

**How to use it:** Restart the bot, send any message. The signal prefixes the response once.

**Good output looks like:**
```
[Bot restart]
User: hey
Bot:  Resuming from last session summary.
      [response to "hey"]
```

**Common mistake:** Expecting the signal on every message. It fires exactly once per startup — on the first message — then clears.

---

## What's Now Possible

- Ask Tintu to help you think through decisions without worrying it will confidently hallucinate code or math
- Set personality preferences once and have every conversation reflect them — including after restarts
- Reference something said three turns ago and have Tintu answer accurately
- Know at session start exactly what context Tintu has — seamless, resumed from summary, or fresh
- Let Tintu keep track of active tasks and surface them naturally in responses
- Recover long sessions into compressed summaries with verbatim key facts that survive across sessions
- Deploy to VPS and have both bots (mithu + friend) running with independent personality configurations
