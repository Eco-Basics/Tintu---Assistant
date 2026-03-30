# Phase 3: Context Budget Manager - Research

**Researched:** 2026-03-28
**Domain:** Conversation history management, session summarization, token budget enforcement, and context assembly for multi-turn Ollama calls
**Confidence:** HIGH

## Summary

Phase 3 wires multi-turn conversation history, session summarization with verbatim key_facts, an 8k-token budget manager, active task injection, and session continuity signals into the Ollama call path. The user can hold conversations across multiple exchanges without repeating context, sessions compress after ~20 turns while preserving specific facts, and the assistant always stays within budget. The codebase already has async DB infrastructure, intent routing, and the build_* response functions — Phase 3 plugs history and task context into these existing call sites, adds conversation_turns table and summarization logic, and enforces token limits before each Ollama request.

**Primary recommendation:** Implement conversation_turns as write-on-every-response + in-memory LRU cache (last 8), wire history prepend + task injection into response_builder.py build_* functions, add conversation_turns schema + migrate conversation_summaries columns in migrations.py, add /summarize intent handling to router.py with async background summarization, implement token counting via character ÷ 4 estimate (validate against Ollama prompt_eval_count in Wave 0 UAT), and enforce budget by trimming oldest history first.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Conversation history storage:**
- Every turn written to `conversation_turns` DB table immediately (source of truth + crash protection)
- In-memory holds last 8 turns as fast list for prompt building (no DB read per message during normal operation)
- On startup/restart: reload last 8 turns from DB, plus session summary + key_facts
- History dict keyed by chat_id (automatic isolation between bots)
- 8 turns (16 messages: 8 user + 8 assistant) per PERS-02

**History prompt format:**
- Prepended as block before user message in Ollama prompt
- Format: `Previous conversation:\nYou: ...\nAssistant: ...\n\nCurrent message: {msg}`
- Flat string (Ollama `/api/generate` takes `prompt` + `system`, not messages array)
- Extraction calls (task, reminder, preference, decision, complete_task) must NOT receive history injection

**Session continuity (CTX-03):**
- "Session" not restart-based; VPS runs 24/7
- On startup with empty in-memory window: reload recent turns from DB for chat_id
  - If turns found: seamless continuity
  - If no turns found: check `conversation_summaries` for most recent summary
  - Signal to user: "Resuming from last session summary." or "No prior session found — starting fresh."
- On restart with DB intact: reload from `conversation_turns` — user doesn't notice
- Signal only shown when window was empty AND no recent turns exist in DB

**Full context on restart:**
- 1. Dynamic system prompt (preferences + traits, from Phase 2)
- 2. Most recent session summary + key_facts from `conversation_summaries` (if any)
- 3. Last 8 turns from `conversation_turns`

**Summarization trigger and flow:**
- Trigger: every 20 turns (hard count since last summary)
- Additional trigger: explicit `/summarize` Telegram command
- Topic-wise automatic summarization deferred to v1.x
- Summary sent to user as Telegram message for review (not silent background write)
- Summary saved to DB immediately (does not block waiting for confirmation)
- User can reply with correction ("actually I decided X not Y") — assistant updates stored `key_facts`
- Summarization runs async (no delay to user's 20th-turn response)

**key_facts vs narrative summary:**
- `summary` column (narrative): flowing story of topics, work, context
- `key_facts` column (verbatim): specific facts that survive word-for-word — names, dates, explicit decisions, preferences. Stored as structured list (JSON or newline-separated). Retrieved precisely.
- Both columns added to existing `conversation_summaries` via additive migration

**Active task injection (CTX-02):**
- Up to 5 most urgent/recent active tasks injected into each answer call via dedicated context slot
- Tasks sourced from `tasks` table (status = 'inbox' or 'active', ordered by priority DESC, created_at DESC)
- Applies to user-facing calls only (same set as history injection) — NOT extraction calls

**Token budget (CTX-01):**
- Hard limit: 8,192 tokens total per Ollama call
- Budget slots (approximate allocation):
  - System prompt (Phase 2): ~500–800 tokens
  - Session summary/key_facts: ~200–400 tokens
  - Active tasks (5): ~100–200 tokens
  - Rolling history (8 turns): ~1,000–2,000 tokens
  - Current message: ~50–500 tokens
  - Reserve for Ollama response: ~2,000–3,000 tokens
- If assembled context exceeds budget: trim history from oldest first, then trim summary, never trim system prompt or active tasks
- Token counting: LEFT TO PLANNER (tiktoken, character ÷ 4 estimate, or Ollama prompt_eval_count)

### Claude's Discretion

- Exact token counting implementation (tiktoken vs character estimate)
- Exact `conversation_turns` table schema (beyond chat_id, role, content, created_at)
- Exact format of key_facts storage (JSON array vs newline list)
- Exact wording of the summarization Telegram message shown to user
- How corrections to key_facts are parsed and applied (free-text reply vs structured command)

### Deferred Ideas (OUT OF SCOPE)

- Topic-wise automatic summarization — detect topic boundaries and summarize when topics shift. Requires per-message topic classification. → v1.x
- named_entities column population — Phase 1 context deferred this to Phase 3. Can be populated during summarization alongside key_facts, but exact extraction strategy deferred.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERS-02 | Rolling conversation history (last 5–8 turns) included in each Ollama call — assistant can hold a topic across multiple exchanges without the user repeating themselves | conversation_turns table + in-memory cache, history prepend to prompt in build_answer/build_retrieval_answer/build_compare_answer, draft_reply also receives history |
| PERS-03 | After ~20 turns, session compressed and stored with narrative summary and verbatim key_facts column — specific decisions and named entities survive summarization | summarization trigger on 20-turn hard count + /summarize command, async background task sends summary to user for review and confirmation, key_facts stored as structured list and retrieved in full context reload |
| CTX-01 | ContextBudgetManager enforces hard per-slot token limits (system prompt, history, retrieved memory, active tasks) — total context stays within 8k window regardless of session length | Token counting strategy (character ÷ 4 or Ollama prompt_eval_count), budget enforcement before Ollama call in response_builder.py, trim history oldest-first if over budget |
| CTX-02 | Up to 5 most urgent/recent active tasks injected into each answer via context budget slot — assistant is aware of current work without user restating it | Query `tasks` table (status = 'inbox' or 'active', order by priority DESC + created_at DESC) in response_builder.py, inject into prompt before Ollama call for user-facing intents only (not extraction) |
| CTX-03 | On first message of new session, assistant signals whether prior session summary is available — user never silently surprised by context reset | On startup: reload conversation_turns for chat_id; if empty, check conversation_summaries; signal "Resuming from last session summary" or "No prior session found — starting fresh" when window was empty and no turns in DB |

</phase_requirements>

---

## Standard Stack

### Core Libraries (Existing in Project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiosqlite | (see requirements.txt) | Async SQLite wrapper for conversation_turns read/write | Project's established async DB pattern; no extra dependencies needed |
| httpx (async) | (see requirements.txt) | Async HTTP client for Ollama API calls | Already in use; supports streaming and timeout handling |
| python-telegram-bot | (see requirements.txt) | Telegram bot framework; handles message dispatch and async tasks | Existing framework; supports asyncio.create_task() for background summarization |

### Supporting Tools (No External Dependency)

| Component | How to Implement | Purpose |
|-----------|-----------------|---------|
| Token counting | Character ÷ 4 estimate (draft 1) + Ollama prompt_eval_count validation (Wave 0) | Quick approximation; validate against actual Ollama response counts in UAT |
| In-memory history cache | Python dict[chat_id: list[dict]] | Fast O(1) history access, repopulated on startup from DB |
| Background summarization | asyncio.create_task() in message handler | Fire-and-forget summary generation after turn 20; no blocking |

### No Hand-Rolled Custom Code Needed

Avoid building:
- Token counting from scratch (use character estimate + Ollama feedback)
- Database connection pooling (aiosqlite connection-per-request is sufficient for single-user bot)
- Message queue system for summarization (asyncio.create_task is enough for single deployment)

---

## Architecture Patterns

### Recommended Project Structure (Additions to Phase 3)

```
app/
├── storage/
│   ├── db.py              # [existing] async DB helpers
│   ├── models.py          # [existing] SCHEMA; ADD conversation_turns + migrate conversation_summaries
│   └── migrations.py       # [existing] run_migrations(); ADD conversation_turns creation + key_facts/named_entities columns
├── llm/
│   ├── response_builder.py # [existing] build_answer, etc.; WIRE history + task injection + budget here
│   ├── ollama_client.py    # [existing] generate() — tracks prompt_eval_count in response
│   └── [NEW] context_manager.py  # Token budget enforcement, history cache, task injection logic
├── memory/
│   ├── summarizer.py       # [existing] summarize_conversation(); EXTEND with key_facts + session signal
│   └── [NEW] conversation_state.py # In-memory history cache, startup reload logic
├── bot/
│   ├── router.py           # [existing] intent dispatch; ADD /summarize intent
│   ├── handlers.py         # [existing] message_handler; CALL conversation_turns.write() + history cache update
│   └── commands.py         # [existing] bot commands; ADD /summarize command handler if needed
└── main.py                 # [existing] post_init; ADD conversation state reload on startup
```

### Pattern 1: Conversation Turn Write-On-Every-Response

**What:** Every user message and assistant response immediately written to `conversation_turns` table (atomic, durable source of truth); in-memory cache holds last 8 turns for fast retrieval during prompt building.

**When to use:** Always. Write happens in message_handler after route() returns, before sending reply to Telegram.

**Example:**
```python
# In app/bot/handlers.py — after route() returns
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    response = await route(user_message)

    # Write both sides to DB
    await write_conversation_turn(chat_id=update.effective_chat.id, role="user", content=user_message)
    await write_conversation_turn(chat_id=update.effective_chat.id, role="assistant", content=response)

    # Update in-memory cache
    history_cache.append(chat_id, {"role": "user", "content": user_message})
    history_cache.append(chat_id, {"role": "assistant", "content": response})

    await update.message.reply_text(response, parse_mode="Markdown")

async def write_conversation_turn(chat_id: int, role: str, content: str) -> int:
    """Write turn to conversation_turns table."""
    return await execute(
        """INSERT INTO conversation_turns (chat_id, role, content, created_at)
           VALUES (?, ?, ?, datetime('now'))""",
        (chat_id, role, content),
    )
```

### Pattern 2: History Prepend Before Ollama Call

**What:** Load last N turns from cache (or DB if cache empty), format as narrative block, prepend to user message before Ollama request.

**When to use:** In all user-facing build_* functions (build_answer, build_retrieval_answer, build_compare_answer, draft_reply). NOT in extraction calls.

**Example:**
```python
# In app/llm/response_builder.py
from app.llm.context_manager import ContextBudgetManager

async def build_answer(message: str, chat_id: int) -> str:
    """Build answer with history + active tasks injected."""
    context_mgr = ContextBudgetManager(chat_id)

    # Load dynamic system prompt (from Phase 2)
    system = await build_system_prompt(chat_id)  # Phase 2 function

    # Assemble full context: history + tasks
    assembled = await context_mgr.assemble_context(message)
    # assembled = {
    #     "history_block": "Previous conversation: You: ... Assistant: ...",
    #     "tasks_block": "Active tasks: 1. Review pitch deck",
    #     "tokens_used": 2456
    # }

    # Build prompt with history prepended
    if assembled["history_block"]:
        prompt = f"{assembled['history_block']}\n\nCurrent message: {message}"
    else:
        prompt = message

    # Inject active tasks as a separate context section in system prompt or prompt
    full_prompt = f"{prompt}\n\n{assembled['tasks_block']}" if assembled["tasks_block"] else prompt

    return await generate(full_prompt, system=system)
```

### Pattern 3: Summarization on 20-Turn Trigger + User Command

**What:** Count turns since last summary; when count reaches 20, trigger async summarization. Also allow `/summarize` command for explicit user control.

**When to use:** In message_handler (automatic every 20 turns) and in router.py (user command).

**Example:**
```python
# In app/bot/handlers.py — after write_conversation_turn
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    response = await route(user_message)
    chat_id = update.effective_chat.id

    await write_conversation_turn(chat_id, "user", user_message)
    await write_conversation_turn(chat_id, "assistant", response)

    # Check if 20 turns since last summary
    turn_count = await get_turn_count_since_last_summary(chat_id)
    if turn_count >= 20:
        # Fire-and-forget summarization
        asyncio.create_task(summarize_and_notify(chat_id, update))

    await update.message.reply_text(response, parse_mode="Markdown")

async def summarize_and_notify(chat_id: int, update: Update):
    """Async task: summarize session and send to user for review."""
    summary = await generate_session_summary(chat_id)
    key_facts = extract_key_facts(summary)  # Claude's discretion

    # Send summary message to user
    await update.bot.send_message(
        chat_id=chat_id,
        text=f"*Session Summary (last 20 turns):*\n\n{summary['narrative']}",
        parse_mode="Markdown"
    )

    # Save to DB
    await execute(
        """INSERT INTO conversation_summaries
           (date, summary, key_facts, named_entities, created_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        (today_str(), summary['narrative'], summary['key_facts'], summary.get('entities', '')),
    )
```

### Pattern 4: Session Continuity Signal on Startup

**What:** On startup or when in-memory cache is empty, reload last 8 turns from DB. If no turns found, check for session summary and signal to user.

**When to use:** In app/main.py post_init hook and at the start of first message handler in a new session.

**Example:**
```python
# In app/main.py
async def post_init(application: Application):
    await run_migrations()
    await ensure_vault_structure()

    # Initialize conversation state
    await load_conversation_state_on_startup()

    logger.info("Assistant ready.")

async def load_conversation_state_on_startup():
    """Reload last 8 turns for each chat_id from DB."""
    # For single-user bot, chat_id is TELEGRAM_USER_ID
    chat_id = TELEGRAM_USER_ID

    last_turns = await fetchall(
        """SELECT role, content, created_at FROM conversation_turns
           WHERE chat_id = ?
           ORDER BY created_at DESC LIMIT 8""",
        (chat_id,),
    )

    if last_turns:
        # Reverse to get chronological order
        history_cache.set(chat_id, list(reversed(last_turns)))
    else:
        # No recent turns; check for summary
        summary = await fetchone(
            """SELECT summary, key_facts FROM conversation_summaries
               WHERE DATE(created_at) <= DATE('now')
               ORDER BY created_at DESC LIMIT 1""",
            ()
        )

        if summary:
            # Will signal on first message
            pending_signal[chat_id] = "session_summary_available"
        else:
            pending_signal[chat_id] = "session_fresh"

# In first message of session, check pending_signal and send signal to user
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Signal session status on first turn
    if chat_id in pending_signal:
        signal = pending_signal.pop(chat_id)
        if signal == "session_summary_available":
            await update.message.reply_text(
                "Resuming from last session summary.",
                parse_mode="Markdown"
            )
        elif signal == "session_fresh":
            await update.message.reply_text("No prior session found — starting fresh.")

    user_message = update.message.text
    response = await route(user_message)
    # ...
```

### Anti-Patterns to Avoid

- **Synchronous DB reads during message handling:** Never block on fetchall() in tight loops. Load history on startup + cache in memory. Writes are OK (INSERT is fast).
- **Unlimited history prepend:** Always trim to last 8 turns max; don't prepend entire conversation history.
- **Summarization blocking user response:** Use asyncio.create_task() to fire-and-forget. Never await summarization during message_handler.
- **Extraction calls receiving history injection:** Keep extraction (task, reminder, decision, etc.) calls history-free. They should extract facts from the current message only, not context.
- **Silent budget overflow:** Always validate assembled context against 8k limit and log if trimming occurs. User should never be surprised by lost history.
- **Trusting character ÷ 4 without validation:** Validate token counts against Ollama's prompt_eval_count in Wave 0 UAT. If off by >10%, recalibrate or switch to tiktoken.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token counting | Custom tokenizer from scratch | Character ÷ 4 estimate (draft 1) + Ollama prompt_eval_count (validation) | Tokenization edge cases (Unicode, subword boundaries) are subtle; Ollama provides ground truth; tiktoken adds dependency |
| Database connection pooling | Custom pool with size limits | aiosqlite connection-per-request (get_db() pattern) | Single-user bot has low concurrency; connection overhead negligible; WAL mode handles multiple readers/writers |
| Message queue for summarization | Custom queue.Queue or Celery | asyncio.create_task() | VPS runs single process; no distributed need; task fires, completes, logs errors. Overkill to add message broker. |
| In-memory cache with TTL | Custom TTL eviction logic | Simple dict[chat_id: list[dict]] + rebuild on restart | For single-user bot, restart is rare; full rebuild on startup is acceptable; TTL complexity not justified. |
| Correction parsing for key_facts | Custom NLP for intent detection | Free-text reply ("actually X") → simple prompt to LLM to extract correction | Let Ollama handle ambiguity. User's correction message is short; LLM can extract the delta reliably. |

**Key insight:** All listed problems have existing solutions in the tech stack or are handled by Ollama itself. Don't add complexity (tokens, queues, parsing) that isn't needed for a single-user 24/7 assistant on a small VPS.

---

## Common Pitfalls

### Pitfall 1: History Cache Out of Sync with DB

**What goes wrong:** In-memory cache diverges from conversation_turns table due to a crash or failed write. On restart, stale cache mixes with DB, losing coherence.

**Why it happens:** Writing to DB happens after updating cache, or cache update fails silently while DB write succeeds.

**How to avoid:**
1. Always write to DB first, then update cache (reversing this order risks cache-only data loss in a crash).
2. On startup, rebuild cache from DB (ignore in-memory state from before shutdown).
3. Log every cache update alongside DB writes; audit trail helps detect drift.

**Warning signs:**
- Cache shows turns not in DB (crash after cache update, before DB flush).
- DB shows turns not in cache (suggests cache truncation or startup rebuild missed some rows).
- Run: `SELECT COUNT(*) FROM conversation_turns WHERE chat_id = ? ORDER BY created_at DESC LIMIT 8` and compare to cache size.

### Pitfall 2: Summarization Blocking the Message Handler

**What goes wrong:** User sends 20th message. Summarization runs synchronously in the message_handler. Model takes 10+ seconds to summarize. User's 20th-turn response is delayed by 10 seconds.

**Why it happens:** Awaiting summarization in the same async context as message_handler.

**How to avoid:**
1. Trigger summarization asynchronously: `asyncio.create_task(summarize_and_notify(chat_id, update))`.
2. Return user's response immediately; let summarization run in background.
3. Log task completion so you can monitor if summaries are being created.

**Warning signs:**
- User reports slow response after 20-turn mark.
- Logs show message_handler duration spiking when turn count hits 20.
- Check: `grep "Saved conversation summary" logs/ | wc -l` — if no entries after messages received, summarization isn't firing.

### Pitfall 3: History Injection into Extraction Calls

**What goes wrong:** Task extraction call receives history prepend. LLM confuses prior task mentions with the current request ("add a task to review the pitch" + history mentioning pitch makes it extract wrong context).

**Why it happens:** Copy-pasting history injection logic into all build_* calls without checking call site.

**How to avoid:**
1. Only inject history in user-facing calls: build_answer, build_retrieval_answer, build_compare_answer, draft_reply.
2. Keep extraction calls (task, reminder, decision, preference, complete_task) history-free.
3. Add a comment at extraction call sites: `# No history injection — extract from current message only`.
4. Review in code inspection: grep for `TASK_EXTRACT_PROMPT` / `REMINDER_EXTRACT_PROMPT` and ensure no history prepend above them.

**Warning signs:**
- Extracted task title doesn't match user's phrasing; seems to reference old context.
- Turn count shows extraction call was made with history prepended (debug log).
- User reports: "I asked it to add task X, but it created task Y from way earlier."

### Pitfall 4: Token Budget Exceeded Silently

**What goes wrong:** Assembled context exceeds 8k tokens, but no trimming happens. Ollama receives oversized prompt; response is corrupted or model refuses to process.

**Why it happens:** Token counting is off (character ÷ 4 underestimates); budget check wasn't run before Ollama call; logging doesn't flag the overage.

**How to avoid:**
1. Before every Ollama call in response_builder.py, call `context_mgr.validate_budget()`.
2. If over budget, trim oldest history (not system prompt or tasks).
3. Log the trim: `logger.warning(f"Budget exceeded {tokens_used}/{8192}. Trimmed {n} turns.")`.
4. In Wave 0 UAT, compare token count estimates against Ollama's `prompt_eval_count` field in every response. Recalibrate if error > 10%.

**Warning signs:**
- No logs of budget validation or trimming (should appear frequently if system is working).
- User reports garbled responses after history builds up.
- Ollama logs show `context_length_exceeded` or model refusing prompt.
- Run: `SELECT SUM(LENGTH(content)) FROM conversation_turns WHERE chat_id = ? ORDER BY created_at DESC LIMIT 8` — if bytes exceed ~32KB, likely over 8k tokens.

### Pitfall 5: Session Signal Never Shown (Missing Startup Reload)

**What goes wrong:** User restarts bot, then sends first message. No signal is shown, even though prior session summary exists.

**Why it happens:** Startup reload logic (`load_conversation_state_on_startup()`) wasn't called, or pending_signal dict wasn't checked in message_handler.

**How to avoid:**
1. Add conversation state reload to app/main.py post_init.
2. Verify post_init is called before message_handler receives first message (Application framework guarantees this).
3. Check pending_signal dict at the very start of message_handler before processing any intent.
4. If pending_signal is missing, log a warning; don't silently skip the signal.

**Warning signs:**
- User says: "I restarted the bot and it doesn't remember my prior session."
- Debug logs show post_init completed but no "conversation state loaded" message.
- Check: `tail logs/ | grep "loaded.*turns"` — should appear on startup.

---

## Code Examples

Verified patterns from existing codebase:

### Pattern: Async DB Write (Existing in app/storage/db.py)

```python
# Source: app/storage/db.py (existing)
async def execute(query: str, params: tuple = ()) -> int:
    async with await get_db() as db:
        cursor = await db.execute(query, params)
        await db.commit()
        return cursor.lastrowid

# Usage in conversation_turns write:
async def write_conversation_turn(chat_id: int, role: str, content: str) -> int:
    return await execute(
        """INSERT INTO conversation_turns (chat_id, role, content, created_at)
           VALUES (?, ?, ?, datetime('now'))""",
        (chat_id, role, content),
    )
```

### Pattern: Async DB Fetch (Existing in app/storage/db.py)

```python
# Source: app/storage/db.py (existing)
async def fetchall(query: str, params: tuple = ()) -> list[dict]:
    async with await get_db() as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

# Usage in history load:
async def load_last_n_turns(chat_id: int, n: int = 8) -> list[dict]:
    return await fetchall(
        """SELECT role, content, created_at FROM conversation_turns
           WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?""",
        (chat_id, n),
    )
```

### Pattern: Intent Router with History Injection (New)

```python
# Source: Phase 3 (to be created in response_builder.py)
async def build_answer(message: str, chat_id: int, system: str = "") -> str:
    """Build answer with rolling history prepended."""
    # Load history from cache or DB
    history = await get_conversation_history(chat_id, max_turns=8)

    # Format history block
    history_block = ""
    if history:
        lines = []
        for turn in history:
            role = "You" if turn["role"] == "user" else "Assistant"
            lines.append(f"{role}: {turn['content']}")
        history_block = "Previous conversation:\n" + "\n".join(lines)

    # Build final prompt
    if history_block:
        prompt = f"{history_block}\n\nCurrent message: {message}"
    else:
        prompt = message

    # Load system prompt (from Phase 2)
    if not system:
        system = await build_system_prompt(chat_id)

    return await generate(prompt, system=system)
```

### Pattern: Background Summarization with asyncio.create_task

```python
# Source: Phase 3 (to be created in handlers.py and summarizer.py)
# In app/bot/handlers.py
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = update.effective_chat.id

    response = await route(user_message)

    # Write to DB
    await write_conversation_turn(chat_id, "user", user_message)
    await write_conversation_turn(chat_id, "assistant", response)

    # Check if summarization needed
    turn_count = await get_turn_count_since_last_summary(chat_id)
    if turn_count >= 20:
        # Fire-and-forget background task
        task = asyncio.create_task(
            summarize_and_notify_user(chat_id, update.message, update.bot)
        )
        logger.debug(f"Summarization task created: {task.get_name()}")

    await update.message.reply_text(response, parse_mode="Markdown")

# In app/memory/summarizer.py
async def summarize_and_notify_user(chat_id: int, msg, bot):
    """Async: summarize session and send to user."""
    try:
        # Get recent turns since last summary
        turns = await fetchall(
            """SELECT role, content FROM conversation_turns
               WHERE chat_id = ? AND created_at > (
                   SELECT COALESCE(MAX(created_at), '2000-01-01')
                   FROM conversation_summaries WHERE chat_id = ?
               )
               ORDER BY created_at ASC""",
            (chat_id, chat_id),
        )

        # Format for LLM
        log = "\n".join([f"{t['role'].title()}: {t['content']}" for t in turns])

        # Summarize
        response = await generate(f"""Summarize this conversation session.

Return this exact format:
Summary: <one paragraph>
Key facts: <comma-separated verbatim facts or decisions>
Entities: <comma-separated names/dates mentioned>

Conversation:
{log}""")

        # Parse response
        parsed = _parse_key_value(response)

        # Send to user for review
        message_text = f"*Session Summary*\n\n{parsed.get('Summary', response)}\n\n_Reply with corrections if needed._"
        await bot.send_message(chat_id=chat_id, text=message_text, parse_mode="Markdown")

        # Save to DB
        await execute(
            """INSERT INTO conversation_summaries
               (chat_id, date, summary, key_facts, named_entities, created_at)
               VALUES (?, DATE('now'), ?, ?, ?, datetime('now'))""",
            (chat_id, parsed.get('Summary', ''), parsed.get('Key facts', ''), parsed.get('Entities', '')),
        )

        logger.info(f"Summarized session for chat_id={chat_id}")
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No conversation history; each message independent | Rolling 8-turn history with DB persistence | This phase (Phase 3) | Users can hold topics across exchanges without repeating context |
| Silent history loss on restart | Startup reload from DB + session signal to user | This phase (Phase 3) | Transparency — user knows if prior context is available |
| Manual session review (end-of-day command) | Automatic summarization every 20 turns + user review/correction | This phase (Phase 3) | Passive memory building; key facts surface automatically |
| No token budget; context grows unbounded | 8k hard limit enforced before Ollama call; history trimmed oldest-first | This phase (Phase 3) | Predictable context; no overflow surprises |
| No task awareness in responses | Active task injection (top 5) on every answer call | This phase (Phase 3) | Assistant is context-aware of current work |

**Deprecated/outdated:**
- None — Phase 3 is the first to add history and budget management. Earlier phases (1, 2) are foundation and system prompt assembly.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4.4 + pytest-asyncio 0.23.8 (from Phase 1 setup) |
| Config file | tests/conftest.py (fixture definitions) + pytest.ini (runner config) |
| Quick run command | `pytest tests/test_context_manager.py -x` (specific module, ~5s) |
| Full suite command | `pytest tests/ -x` (all tests, ~30s including DB schema tests) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERS-02 | Rolling history (last 8 turns) prepended to prompt before Ollama call | integration | `pytest tests/test_response_builder.py::test_build_answer_with_history -xvs` | ❌ Wave 0 |
| PERS-02 | History excludes extraction calls (task, reminder, decision, etc.) | unit | `pytest tests/test_response_builder.py::test_task_extract_no_history -xvs` | ❌ Wave 0 |
| PERS-03 | Summarization triggered every 20 turns (hard count) | unit | `pytest tests/test_summarizer.py::test_summarize_on_20_turns -xvs` | ❌ Wave 0 |
| PERS-03 | Session summary sent to user as Telegram message for review | integration | `pytest tests/test_summarizer.py::test_summary_message_sent -xvs` | ❌ Wave 0 |
| PERS-03 | key_facts and named_entities columns added to conversation_summaries | unit | `pytest tests/test_migrations.py::test_conversation_summaries_columns_exist -xvs` | ❌ Wave 0 |
| CTX-01 | Assembled context never exceeds 8,192 tokens (validated against Ollama prompt_eval_count) | integration | `pytest tests/test_context_manager.py::test_token_budget_enforced -xvs` | ❌ Wave 0 |
| CTX-01 | History trimmed oldest-first when budget exceeded | unit | `pytest tests/test_context_manager.py::test_trim_history_oldest_first -xvs` | ❌ Wave 0 |
| CTX-02 | Top 5 active tasks injected into user-facing calls (build_answer, build_retrieval_answer, etc.) | unit | `pytest tests/test_context_manager.py::test_active_tasks_injected -xvs` | ❌ Wave 0 |
| CTX-02 | Active tasks NOT injected into extraction calls | unit | `pytest tests/test_response_builder.py::test_task_extract_no_tasks_injection -xvs` | ❌ Wave 0 |
| CTX-03 | On startup with empty in-memory window, signal "Resuming from last session summary" if summary exists in DB | unit | `pytest tests/test_conversation_state.py::test_session_signal_on_startup -xvs` | ❌ Wave 0 |
| CTX-03 | On startup with no prior turns and no summary, signal "No prior session found — starting fresh" | unit | `pytest tests/test_conversation_state.py::test_session_signal_fresh_start -xvs` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_response_builder.py tests/test_context_manager.py -x` (10–15s, covers PERS-02 + CTX-01/02)
- **Per wave merge:** `pytest tests/ -x` (full suite, 30s, all 5 waves)
- **Phase gate:** Full suite green + manual UAT: (1) send 5 messages, verify history in prompt; (2) reach 20 turns, verify summarization fires and summary message sent; (3) restart bot, verify session signal shown; (4) check Ollama logs for prompt_eval_count vs estimated tokens (should be ±10%).

### Wave 0 Gaps

- [ ] `tests/test_context_manager.py` — Token counting, budget enforcement, history trim logic (CTX-01)
- [ ] `tests/test_response_builder.py` — History injection in build_* functions, no injection in extractions (PERS-02, CTX-02)
- [ ] `tests/test_summarizer.py` — 20-turn trigger, summary message sending, key_facts extraction (PERS-03)
- [ ] `tests/test_conversation_state.py` — Startup reload, session signal logic (CTX-03)
- [ ] `tests/test_migrations.py` — conversation_turns table creation, conversation_summaries columns added (existing but verify adds are schema-compatible)
- [ ] Framework install: (from Phase 1) `pip install pytest==7.4.4 pytest-asyncio==0.23.8` — if not yet done
- [ ] conftest.py shared fixtures: async_db context manager, sample_turns fixture, mock_ollama_response fixture

---

## Open Questions

1. **Token counting implementation — character ÷ 4 vs tiktoken?**
   - What we know: Character ÷ 4 is a quick estimate; tiktoken is accurate but adds a dependency.
   - What's unclear: How much error is acceptable? (CONTEXT.md says "LEFT TO PLANNER" but no tolerance specified.)
   - Recommendation: Start with character ÷ 4 in Phase 3 Wave 0. Validate against Ollama's `prompt_eval_count` field in UAT. If error > 10%, switch to tiktoken in next phase or UAT hotfix.

2. **Exact schema for conversation_turns table — what columns beyond (chat_id, role, content, created_at)?**
   - What we know: Minimum needed is chat_id (isolation), role (user/assistant), content (the message), created_at (ordering).
   - What's unclear: Should we add message_id (for Telegram integration)? turn_index (for session boundaries)? metadata (JSON)?
   - Recommendation: Start with (id, chat_id, role, content, created_at). Add columns if needed during Wave 0 UAT (e.g., if user reports trouble with session boundaries).

3. **Format of key_facts storage — JSON array vs newline-separated list?**
   - What we know: Must be retrievable as-is (verbatim, no re-parsing). Can be stored as TEXT.
   - What's unclear: Which is easier to query/display? (JSON requires CAST or JSON operators; newline list requires split().)
   - Recommendation: Use newline-separated list (one fact per line) for simplicity. If facts contain newlines (unlikely for short verbatim facts), escape them with `\n`. Revisit if queries become complex.

4. **Exact wording of the summarization Telegram message shown to user?**
   - What we know: Must invite user to review and correct key_facts.
   - What's unclear: Should it show the full summary, just key_facts, or both?
   - Recommendation: Show narrative summary + key_facts separately. Let planner finalize wording during Wave 0. Start with: `*Session Summary (last 20 turns):*\n\n{narrative}\n\n*Key facts:*\n{key_facts}\n\n_Reply with corrections if needed._`

5. **How to parse corrections to key_facts?**
   - What we know: User replies with free text ("actually I decided X not Y").
   - What's unclear: Do we need a structured command format, or can we ask LLM to extract the correction?
   - Recommendation: Use free text + LLM extraction. On receiving a reply after summary message, run: `extract_correction(user_reply) -> {"original": "...", "corrected": "..."}` via Ollama. Update key_facts in DB. Simple and flexible. If users find it confusing, add a structured format (e.g., `/correct key_fact_1: new_value`) in v1.x.

---

## Sources

### Primary (HIGH confidence)

- **Existing codebase**: `app/storage/db.py`, `app/llm/response_builder.py`, `app/bot/router.py`, `app/bot/handlers.py`, `app/storage/models.py`, `app/storage/migrations.py`, `app/memory/summarizer.py`
  - Async pattern (aiosqlite), intent routing, message handling, migration schema established
- **Phase 2 CONTEXT.md** (`.planning/phases/02-promptbuilder/02-CONTEXT.md`)
  - Call sites for history injection: build_answer, build_retrieval_answer, build_compare_answer, draft_reply in response_builder.py; draft_reply in router.py
  - Extraction calls (task, reminder, preference, decision, complete_task) must NOT receive history
  - build_system_prompt() interface (Phase 2 outcome)
- **Phase 1 CONTEXT.md** (`.planning/phases/01-foundation/01-CONTEXT.md`)
  - conversation_summaries table schema (id, date, summary, topics, projects, actions, decisions, source_message_range)
  - key_facts + named_entities columns deferred to Phase 3 (this phase)
  - preferences, personality_traits, personas tables (upstream context)

### Secondary (MEDIUM confidence)

- **Phase 3 CONTEXT.md** (`.planning/phases/03-context-budget-manager/03-CONTEXT.md`)
  - User decisions on architecture, schema, UX (locked decisions from discussion phase)
  - Decision to leave token counting, schema exact format, and correction parsing to Claude's discretion
- **REQUIREMENTS.md** (`.planning/REQUIREMENTS.md`)
  - PERS-02, PERS-03, CTX-01, CTX-02, CTX-03 acceptance criteria (source of truth for what counts as "done")

### Tertiary (LOW confidence)

- None at this stage. All critical decisions are documented in locked CONTEXT.md or existing code.

---

## Metadata

**Confidence breakdown:**

| Domain | Level | Reason |
|--------|-------|--------|
| Standard stack (async patterns, DB helpers, intent routing) | HIGH | Existing code establishes patterns; no external research needed; aiosqlite + httpx already in use |
| Architecture (history cache, summarization trigger, startup reload) | HIGH | User decisions locked in CONTEXT.md; integration points clear from reading Phase 2 code |
| Token counting implementation | MEDIUM | Character ÷ 4 is a common heuristic; validation against Ollama prompt_eval_count deferred to UAT; tiktoken adds dependency with tradeoffs |
| Pitfalls | HIGH | Identified from common async Python patterns (cache coherence, task blocking, history leakage); verified against project's async architecture |
| Test coverage | HIGH | Phase 1 established pytest infrastructure; requirements map directly to test cases; no ambiguity on what to test |

**Research date:** 2026-03-28
**Valid until:** 2026-04-27 (30 days — stable domain, no fast-moving dependencies)

---

**Phase:** 03-context-budget-manager
**Research completed:** 2026-03-28
