# Phase 3: Context Budget Manager - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire rolling conversation history, session summarization with key_facts, 8k token budget enforcement, active task injection, and session continuity signal into every Ollama call. Phase 2 delivered the dynamic system prompt; Phase 3 adds the conversation layer on top of it. No personality trait detection, no UI changes — this is the memory and context infrastructure.

</domain>

<decisions>
## Implementation Decisions

### Conversation history storage

- **Hybrid architecture**: every turn is written to a `conversation_turns` DB table immediately as it happens — this is the source of truth and crash protection
- In-memory holds the last 8 turns as a fast list for prompt building on each request — no DB read per message during normal operation
- On startup/restart, reload last 8 turns from `conversation_turns` for the chat_id to repopulate the in-memory window — restart is nearly invisible to the user
- History dict is keyed by `chat_id`; isolation between bots is automatic (separate systemd processes, separate DBs)
- **Turn limit for injection**: 8 turns (16 messages: 8 user + 8 assistant) per PERS-02

### History prompt format

- Rolling history is prepended as a block before the user message in the Ollama prompt
- Format: `Previous conversation:\nYou: ...\nAssistant: ...\n\nCurrent message: {msg}`
- This is a flat string (Ollama `/api/generate` takes `prompt` + `system`, not a messages array)
- Extraction calls (task, reminder, preference, decision, complete_task) must NOT receive history injection — same rule as dynamic system prompt from Phase 2

### Session continuity (CTX-03)

- "Session" is not restart-based — the VPS runs 24/7 and restarts are edge cases, not normal operation
- On startup (in-memory window is empty): check `conversation_turns` DB for recent turns for this chat_id
  - If turns found: reload into memory (seamless continuity)
  - If no turns found (genuinely first session or DB wiped): check `conversation_summaries` for most recent summary
  - Signal to user: "Resuming from last session summary." or "No prior session found — starting fresh."
- On restart with DB intact: reload from `conversation_turns` — user doesn't notice the restart
- The signal is only shown when the window was empty AND no recent turns exist in DB

### Full context on restart

- On startup, the assistant loads the FULL layered context:
  1. Dynamic system prompt (preferences + traits, from Phase 2)
  2. Most recent session summary + key_facts from `conversation_summaries` (if any)
  3. Last 8 turns from `conversation_turns`
- This means the assistant "wakes up" knowing the user's personality layer AND their recent concerns — not just raw turns

### Summarization trigger and flow

- **Trigger**: every 20 turns (hard count since last summary), counted from `conversation_turns`
- **Additional trigger**: explicit `/summarize` Telegram command — user can trigger summarization anytime
- Topic-wise automatic summarization (detect topic boundaries) is deferred to v1.x
- The existing `end_of_day_review` intent is kept separate from summarization — it produces a daily review, not a session compression

### Summarization UX — user-visible

- When summarization fires, the summary is **sent to the user as a Telegram message** for review — not a silent background write
- Summary is saved to DB immediately (does not block waiting for confirmation)
- If user replies with a correction ("actually I decided X not Y"), the assistant updates the stored `key_facts` entry
- Summarization runs as an async background task so the user's 20th-turn response is not delayed

### key_facts vs narrative summary

- **`summary` column (narrative)**: what happened in this session — the flowing story of topics, work, and context. Helps the assistant understand what you were working on.
- **`key_facts` column (verbatim)**: specific facts that must survive word-for-word — names, dates, explicit decisions made, preferences stated. Stored as a structured list (JSON or newline-separated). Retrieved precisely.
- Both columns are added to the existing `conversation_summaries` table via an additive migration (Phase 1 deferred this)

### Active task injection (CTX-02)

- Up to 5 most urgent/recent active tasks injected into each answer call via a dedicated context slot
- Tasks sourced from existing `tasks` table (status = 'inbox' or 'active', ordered by priority DESC, created_at DESC)
- Task injection applies to user-facing calls only (same set as history injection) — not extraction calls

### Token budget (CTX-01)

- Hard limit: 8,192 tokens total per Ollama call
- Budget slots (approximate allocation — planner to validate exact numbers):
  - System prompt (Phase 2): ~500–800 tokens
  - Session summary/key_facts: ~200–400 tokens
  - Active tasks (5): ~100–200 tokens
  - Rolling history (8 turns): ~1,000–2,000 tokens
  - Current message: ~50–500 tokens
  - Reserve for Ollama response: ~2,000–3,000 tokens
- If assembled context exceeds budget: trim history from oldest first, then trim summary, never trim system prompt or active tasks
- Token counting strategy: **Claude's Discretion** (tiktoken, character ÷ 4 estimate, or Ollama prompt_eval_count) — left to planner to validate against PERS-02 accuracy requirements

### Claude's Discretion

- Exact token counting implementation (tiktoken vs character estimate)
- Exact `conversation_turns` table schema (beyond chat_id, role, content, created_at)
- Exact format of key_facts storage (JSON array vs newline list)
- Exact wording of the summarization Telegram message shown to user
- How corrections to key_facts are parsed and applied (free-text reply vs structured command)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — PERS-02 (rolling history), PERS-03 (session summarization + key_facts), CTX-01 (token budget), CTX-02 (active task injection), CTX-03 (continuity signal) acceptance criteria

### Prior phase context (upstream decisions this phase builds on)
- `.planning/phases/01-foundation/01-CONTEXT.md` — `conversation_summaries` table schema, `key_facts` + `named_entities` columns deferred to Phase 3; `personality_traits`, `personas`, `preferences` table specs
- `.planning/phases/02-promptbuilder/02-CONTEXT.md` — call sites that receive dynamic system prompt (build_answer, build_retrieval_answer, build_compare_answer, draft_reply); extraction calls that must NOT receive context injection; build_system_prompt() interface

### Live code to read before planning
- `app/llm/response_builder.py` — the 3 build_* functions that need history + budget manager wired in
- `app/bot/router.py` — draft_reply call site; where /summarize command will be added
- `app/storage/models.py` — existing conversation_summaries schema (to plan additive migration for key_facts + named_entities)
- `app/storage/db.py` — fetchall/fetchone/execute helpers; how conversation_turns table will be read/written
- `app/storage/migrations.py` — existing migration pattern for adding new tables/columns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/storage/db.py` — `fetchall()`, `fetchone()`, `execute()`: all async helpers, used as-is for conversation_turns reads/writes
- `app/storage/migrations.py` — `run_migrations()` pattern: add new columns to conversation_summaries and new conversation_turns table via `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS`
- `app/storage/models.py` — `conversation_summaries` table already exists; needs `key_facts TEXT` and `named_entities TEXT` columns added
- `app/bot/router.py` — intent dispatch pattern: `/summarize` added as a new intent or as a Telegram command handler in commands.py
- `app/llm/ollama_client.py` — `generate(prompt, system)`: both params already exist; history is injected into `prompt`, system prompt unchanged

### Established Patterns
- All storage calls use `async with await get_db()` — conversation_turns writes follow the same pattern
- Intent router handles all Telegram input — /summarize fits as a new branch in router.py or as a bot command in commands.py
- Background tasks: python-telegram-bot supports `asyncio.create_task()` for fire-and-forget async work

### Integration Points
- `build_answer()`, `build_retrieval_answer()`, `build_compare_answer()` in `app/llm/response_builder.py` — these receive the assembled prompt; history prepend + budget check added here
- `app/bot/router.py` `draft_reply` branch — also needs history injection
- `app/main.py` or bot startup — where `conversation_turns` reload on startup is triggered

</code_context>

<specifics>
## Specific Ideas

- User explicitly wants to see the summary when it's generated — it's a user-facing feature, not a silent background process
- User can correct key_facts after seeing the summary ("actually I decided X not Y")
- The assistant should feel continuous — the VPS runs 24/7, restarts are edge cases, and the goal is that the user never notices a restart happened
- "The last 8 turn capture is just to maintain continuity and not feel like a restart — the full context on startup should reflect the concerns of the user captured through the assistance so far"

</specifics>

<deferred>
## Deferred Ideas

- **Topic-wise automatic summarization** — detect topic boundaries and summarize when topics shift, not just on turn count. Requires per-message topic classification. → v1.x
- **named_entities column population** — Phase 1 context deferred `named_entities` to Phase 3. Can be populated during summarization alongside key_facts, but exact extraction strategy is Claude's discretion or a future pass.

</deferred>

---

*Phase: 03-context-budget-manager*
*Context gathered: 2026-03-28*
