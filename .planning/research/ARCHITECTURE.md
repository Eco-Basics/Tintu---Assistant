# Architecture Research

**Domain:** Adaptive AI assistant — personality layer + context budget manager + multi-session subprocess manager
**Researched:** 2026-03-27
**Confidence:** HIGH (based on direct codebase analysis)

## Current System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     Telegram Bot Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ handlers.py  │  │ commands.py  │  │      jobs.py          │   │
│  │ (msg entry)  │  │ (/commands)  │  │  (reminder checks)    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘   │
│         │                 │                                       │
├─────────▼─────────────────▼──────────────────────────────────────┤
│                     Routing / Intent Layer                        │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  router.py  →  classify()  →  if/elif intent dispatch     │   │
│  └───────────────────────────────────────────────────────────┘   │
│         │                                                         │
├─────────▼─────────────────────────────────────────────────────────┤
│         │           LLM Layer                                     │
│  ┌──────▼───────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ classifier   │  │  response_builder │  │  ollama_client   │   │
│  │ (intent cls) │  │  (answer builds)  │  │  generate(p, s)  │   │
│  └──────────────┘  └──────────────────┘  └──────────────────┘   │
│         │                │                        │               │
│  ┌──────▼───────┐  ┌─────▼────────────┐           │               │
│  │  prompts.py  │  │  SYSTEM_PROMPT   │ ◄─ static constant        │
│  │  (templates) │  │  (hardcoded str) │                           │
│  └──────────────┘  └──────────────────┘                           │
├────────────────────────────────────────────────────────────────────┤
│              Planning / Memory / Storage Layers                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ planning │  │  memory  │  │ storage  │  │  SQLite DB        │  │
│  │  tasks   │  │  vault   │  │  db.py   │  │  (preferences,    │  │
│  │ routines │  │retrieval │  │  models  │  │  conv_summaries,  │  │
│  │schedules │  │comparison│  │migrations│  │  message_log, ...) │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

The three new components slot into this diagram between the Routing Layer and the LLM Layer.

## Integration Target: Where New Components Connect

The critical integration point is the path from `message_handler()` → `route()` → `build_answer()` → `generate()`. Currently:

```
route(message: str)
    └── build_answer(message)
            └── generate(message, system=SYSTEM_PROMPT)
                                         ▲
                                    static string
```

After integration:

```
route(message: str, session_ctx: SessionContext)
    │
    ├── [pre-route] PromptBuilder.build(session_ctx) → dynamic_system_prompt
    │
    └── build_answer(message, dynamic_system_prompt, context_budget)
            └── generate(budgeted_prompt, system=dynamic_system_prompt)
                                                        ▲
                                                   dynamic, per-request
```

## New Components

### Component 1: Dynamic System Prompt Builder

**Location:** `app/llm/prompt_builder.py`

**Responsibility:** Assembles the system prompt string for each request by reading personality traits and behavior preferences from the database, then composing them into a token-aware string.

**Input:** DB connection (async), session context (optional active persona override)
**Output:** `str` — fully assembled system prompt, within token budget

**Slot budget it owns:** System prompt slot (recommended: ~300-500 tokens of the ~8k window)

**What it reads:**
- `preferences` table — all `key/value` rows (existing table, existing data)
- New `personality_traits` table — detected signals like "be direct", "act as coach"
- New `personas` table (optional) — named presets like "brutally honest advisor"

**Communicates with:**
- Storage layer (reads preferences, traits, personas)
- Context Budget Manager (receives token limit, reports actual usage)

**Does NOT:**
- Write to DB (read-only at prompt-build time)
- Know about message content (prompt assembly is user-profile-scoped, not message-scoped)
- Classify or detect personality signals (that is the router's job on `update_preference` intent)

---

### Component 2: Context Budget Manager

**Location:** `app/llm/context_budget.py`

**Responsibility:** Enforces token limits across all slots of the final prompt. Decides what to include, truncate, or omit. Triggers session summarization when turn count threshold is reached.

**Input:**
- System prompt (from PromptBuilder)
- Active tasks (from planning layer)
- Retrieved memory (from retrieval layer)
- Conversation history (from `message_log` or session state)
- Message text (user's current message)

**Output:** `ContextPacket` dataclass containing assembled slots ready to hand to `generate()`

**Slot budget table (hard limits for Qwen3:4b ~8k window):**

| Slot | Token Budget | Source |
|------|-------------|--------|
| System prompt | 400 tokens | PromptBuilder output |
| Active tasks | 200 tokens | planning.list_tasks() capped at 5 |
| Retrieved memory | 300 tokens | retrieval.retrieve_context() relevance-filtered |
| Conversation history | 500 tokens | message_log rolling window |
| User message | variable | current message |
| Response headroom | ~1000 tokens | reserved for model output |
| Total available | ~6500 tokens | leaves buffer under 8k |

**Communicates with:**
- PromptBuilder (receives assembled system prompt)
- Planning layer (fetches active tasks)
- Memory/retrieval layer (fetches relevant context)
- Storage layer (reads/writes `conversation_summaries`, reads `message_log`)

**Summarization trigger:** When session turn count exceeds ~20 turns, the budget manager calls `summarize_session()` which writes a row to `conversation_summaries` (schema already exists) and clears in-memory history. Next session loads the summary via `retrieve_context()`, not pre-loaded into history slot.

**Does NOT:**
- Assemble personality (delegated to PromptBuilder)
- Make routing decisions (belongs to router)
- Store messages (that is `message_log` + `execute()` in handlers.py)

---

### Component 3: Multi-Session Subprocess Manager

**Location:** `app/claude/session_manager.py`

**Responsibility:** Manages a pool of named `claude` CLI subprocesses, one per Telegram topic (project). Routes messages from a specific topic to its corresponding process, returns responses to Telegram.

**Input:** Telegram `message_thread_id` (topic ID), message text
**Output:** Response string from `claude` CLI subprocess

**Session registry:** In-memory `dict[int, ClaudeSession]` mapping `thread_id → process handle + working directory`. Optionally persisted to a lightweight JSON file for restart recovery.

**Communicates with:**
- Telegram bot layer — receives messages with `message_thread_id` present
- Filesystem — each session has its own working directory under `{BASE_DIR}/projects/{topic_slug}/`
- `claude` CLI process — via stdin/stdout subprocess pipe

**Does NOT:**
- Interact with Ollama (entirely separate code path from Goal 1 assistant)
- Share state with the intent router (Goal 1 and Goal 2 are parallel tracks)
- Use the SQLite DB for session state (subprocess handles its own state via `~/.claude/` history)

**Isolation guarantee:** Goal 2 is a separate Telegram group (Forum/Topics mode). The message handler branches at the entry point — if `update.message.chat.id == CLAUDE_GROUP_ID`, it goes to the subprocess manager; otherwise it goes to the existing intent router. Zero cross-contamination.

## Component Boundaries (What Talks to What)

```
┌────────────────────────────────────────────────────────────────────┐
│  handlers.py  (entry point — owns the branch)                     │
│                                                                    │
│    if chat_id == CLAUDE_GROUP_ID:                                  │
│        → ClaudeSessionManager (Goal 2 path)                       │
│    else:                                                           │
│        → route(message, session_ctx)  (Goal 1 path — unchanged)   │
└────────────────────────────────────────────────────────────────────┘

Goal 1 path (adaptive assistant):
─────────────────────────────────
route()
  │
  ├── [intent classify]  ← unchanged
  │
  ├── [pre-generation]
  │     ├── PromptBuilder.build(user_id) → system_prompt_str
  │     └── ContextBudgetManager.assemble(message, system_prompt) → ContextPacket
  │
  ├── [intent handlers]  ← unchanged (create_task, set_reminder, etc.)
  │     These do NOT need context budget — they call generate() with
  │     extraction prompts only, not the full context packet.
  │
  └── [answer/draft/retrieval handlers]  ← context packet injected here
        generate(packet.prompt, system=packet.system)

Goal 2 path (Claude CLI):
──────────────────────────
handlers.py (topic message)
  → ClaudeSessionManager.send(thread_id, message)
      → subprocess stdin write
      → subprocess stdout read (streaming or blocking)
  → reply to Telegram topic
```

## Data Flow

### Goal 1: Adaptive Personality + Context Budget

```
User message (Telegram)
        │
        ▼
handlers.py → message_log INSERT (existing)
        │
        ▼
route(message, session_ctx)
        │
        ├── classify(message)  → intent string (unchanged)
        │
        ├── [if answer/draft/retrieval intent:]
        │       │
        │       ├── PromptBuilder.build()
        │       │       reads: preferences, personality_traits, active_persona
        │       │       returns: system_prompt_str (~300-500 tokens)
        │       │
        │       ├── ContextBudgetManager.assemble()
        │       │       reads: message_log (recent turns), list_tasks(), retrieve_context()
        │       │       checks: turn_count → trigger summarize_session() if >= 20
        │       │       returns: ContextPacket(system, history, tasks, memory, message)
        │       │
        │       └── generate(ContextPacket.prompt, system=ContextPacket.system)
        │               → Ollama API call
        │               → response string
        │
        └── [all other intents: create_task, set_reminder, etc.]
                → unchanged, use extraction prompts without personality context
                → EXCEPT update_preference: also triggers personality signal detection

Response → Telegram reply
```

### Goal 2: Claude CLI Subprocess

```
Telegram Forum Group message (thread_id = topic)
        │
        ▼
handlers.py  [branch: chat_id == CLAUDE_GROUP_ID]
        │
        ▼
ClaudeSessionManager.send(thread_id, message)
        │
        ├── lookup or spawn: subprocess for thread_id
        │       working_dir = BASE_DIR/projects/{topic_slug}/
        │       process = asyncio.create_subprocess_exec("claude", ...)
        │
        ├── write message to process.stdin
        │
        └── read response from process.stdout (with timeout)
                │
                ▼
        reply_text() → Telegram topic thread
```

### Personality Signal Detection Flow

```
update_preference intent (existing)
        │
        ▼
PREFERENCE_EXTRACT_PROMPT → generate() → key/value
        │
        ├── [existing] INSERT INTO preferences
        │
        └── [new] PersonalitySignalDetector.classify(key, value)
                → if signal_type in ["tone", "style", "persona", "behavior"]:
                        INSERT INTO personality_traits
```

### Session Summarization Flow

```
ContextBudgetManager.assemble()
        │
        ├── turn_count = count recent message_log rows for user
        │
        └── [if turn_count >= 20]
                │
                ├── fetch last N turns from message_log
                ├── generate(SUMMARIZE_SESSION_PROMPT, turns)
                ├── INSERT INTO conversation_summaries (schema exists)
                └── clear in-memory session turn counter
                        (summary is now available via retrieve_context(),
                         NOT pre-loaded into next session's history slot)
```

## Recommended Project Structure (additions only)

```
app/
├── llm/
│   ├── classifier.py          # existing — unchanged
│   ├── ollama_client.py       # existing — unchanged
│   ├── prompts.py             # existing — add SUMMARIZE_SESSION_PROMPT
│   ├── response_builder.py    # existing — update to accept ContextPacket
│   ├── prompt_builder.py      # NEW — reads DB, assembles system prompt
│   └── context_budget.py      # NEW — token budgeting, slot assembly, summarization trigger
│
├── bot/
│   ├── handlers.py            # existing — add Goal 2 branch at top
│   ├── router.py              # existing — add session_ctx parameter, inject context packet
│   ├── commands.py            # existing — no change
│   └── jobs.py                # existing — no change
│
├── claude/                    # NEW package — Goal 2 only
│   ├── __init__.py
│   └── session_manager.py     # NEW — subprocess lifecycle, stdin/stdout bridge
│
└── storage/
    ├── models.py              # existing — add personality_traits, personas tables
    └── migrations.py          # existing — migrations run at startup, safe to add tables
```

## Build Order (Dependencies)

The three components have hard dependencies on each other and on existing code. Build in this order:

### Phase 1: PromptBuilder (no dependencies on new code)

Can be built and tested in isolation. Depends only on the existing `preferences` table (already populated by `update_preference` intent) and the new `personality_traits` table (schema migration only).

- Add `personality_traits` and `personas` tables to `models.py`
- Implement `app/llm/prompt_builder.py`
- Wire into `build_answer()` and `build_retrieval_answer()` in `response_builder.py`
- System prompt is now dynamic. No other changes yet.

**Validation:** `update_preference` still works. Answer quality improves with stored preferences. No breakage to any other intent.

### Phase 2: Context Budget Manager (depends on PromptBuilder)

Depends on PromptBuilder being complete (needs the assembled system prompt to calculate remaining budget). Also depends on `message_log` for history (existing).

- Implement `app/llm/context_budget.py`
- Implement `ContextPacket` dataclass
- Update `response_builder.py` to accept and use `ContextPacket`
- Update `route()` signature to accept and pass through `session_ctx`
- Add `SUMMARIZE_SESSION_PROMPT` to `prompts.py`
- Implement `summarize_session()` inside `context_budget.py`

**Validation:** Token counts stay under 8k. Active tasks appear in answers. Session compression fires after 20 turns. All extraction-only intents (create_task, set_reminder, etc.) are unaffected — they do NOT receive a context packet.

### Phase 3: Multi-Session Subprocess Manager (independent of Phase 1-2)

Goal 2 is architecturally isolated from Goal 1. Can be built after Phase 1 and 2, or in parallel since it has zero shared state.

- Configure Telegram group in Forum/Topics mode
- Implement `app/claude/session_manager.py`
- Add `CLAUDE_GROUP_ID` to `app/config.py`
- Add Goal 2 branch in `handlers.py`
- Implement spawn, restart, and graceful shutdown logic

**Validation:** Each topic maps to exactly one `claude` process. Messages in topic A never appear in topic B's process. Bot restart recovers sessions.

## Architectural Patterns

### Pattern 1: Context Packet (Immutable Assembly Before Generation)

**What:** All prompt assembly happens in one place (`ContextBudgetManager.assemble()`) before `generate()` is called. The packet is an immutable dataclass. No prompt string manipulation happens inside `generate()` or the router.

**When to use:** Any time the answer/draft/retrieval intents call `generate()` with full context.

**Why:** Centralizes token counting. Makes testing trivial — assert on packet contents, not on Ollama responses. Prevents drift where one code path includes personality and another does not.

**Example:**
```python
@dataclass(frozen=True)
class ContextPacket:
    system: str          # assembled by PromptBuilder
    history: str         # recent turns, budget-trimmed
    memory: str          # retrieved context, relevance-filtered
    tasks: str           # active tasks, capped at 5
    message: str         # user's current message

    @property
    def prompt(self) -> str:
        parts = []
        if self.memory:
            parts.append(f"Memory:\n{self.memory}")
        if self.tasks:
            parts.append(f"Active tasks:\n{self.tasks}")
        if self.history:
            parts.append(f"Recent conversation:\n{self.history}")
        parts.append(self.message)
        return "\n\n".join(parts)
```

### Pattern 2: Intent Router Stays Dumb

**What:** The router (`router.py`) does NOT know about personality, context budgets, or sessions. It receives a `session_ctx` object and passes it to helpers that need it. It does not inspect or transform it.

**When to use:** Always. The router's job is dispatch, not context management.

**Why:** Prevents the router from becoming a God Object. The existing 200-line router already handles 15 intents — adding context assembly inside the `if/elif` blocks would make it unmaintainable.

**Boundary:** `session_ctx` flows through the router as an opaque pass-through. Only `build_answer()`, `build_retrieval_answer()`, and `build_draft()` unpack it.

### Pattern 3: Extraction Intents are Context-Free

**What:** Intents that extract structured data (`create_task`, `set_reminder`, `create_routine`, `complete_task`, `update_preference`, `capture_note`) do NOT receive the context packet. They call `generate()` with only their extraction prompt.

**Why:** Extraction prompts need precision, not personality. Injecting 500 tokens of personality and history into a prompt that must output `Title: X\nDue: Y` degrades extraction reliability. The 8k window is better spent on actual answer quality.

**Rule:** Context packet only for intents that generate a response the user will read as natural language.

### Pattern 4: Goal 2 Branch at Entry, Not in Router

**What:** The fork between Goal 1 (Ollama assistant) and Goal 2 (Claude CLI) happens in `handlers.py`, before `route()` is called. The router never sees Goal 2 messages.

**When to use:** Any new Telegram group/context that requires a completely different processing path.

**Why:** Goal 2 and Goal 1 share nothing at runtime. Routing them through the same `route()` function would require adding `chat_id` checks throughout the router — a smell that indicates the branch belongs at the top.

## Anti-Patterns

### Anti-Pattern 1: Injecting Context Into the Static SYSTEM_PROMPT Constant

**What people do:** Modify `SYSTEM_PROMPT` in `prompts.py` to include f-string placeholders, then format it with preferences at every call site.

**Why it's wrong:** `SYSTEM_PROMPT` is imported by multiple modules (router.py imports it directly). Formatting it at the call site means each call site formats it differently, leading to drift. Making it an f-string breaks the existing `build_answer()` calls that reference it directly.

**Do this instead:** Keep `SYSTEM_PROMPT` as a fallback constant. `PromptBuilder.build()` returns a new string derived from it but augmented with DB data. Pass the result as `system=` to `generate()`. The constant remains unchanged.

### Anti-Pattern 2: Passing Full Conversation History as System Prompt

**What people do:** Append the last N turns to the system prompt string, treating the system role as a context dump.

**Why it's wrong:** Conversation history belongs in the user/assistant turn structure (the `prompt` field for Ollama), not the system field. System prompt is for persistent instructions and personality. Mixing them makes token counting ambiguous and confuses the model about what is instruction vs. memory.

**Do this instead:** System prompt = personality + capabilities. History = last N turns formatted as `User: ...\nAssistant: ...` in the `prompt` field. The `ContextPacket.prompt` property handles this assembly.

### Anti-Pattern 3: Per-Message personality_traits Table Scans

**What people do:** On every message, query all personality traits, iterate, and build the system prompt from scratch, doing string joins in a loop.

**Why it's wrong:** On a busy session, this is a DB query on every message. The traits rarely change.

**Do this instead:** Cache the assembled system prompt string in memory with a short TTL (e.g., invalidate on `update_preference` intent). Most requests hit the cache. Only rebuild when preferences change.

### Anti-Pattern 4: Sharing subprocess stdout between Topics

**What people do:** Create one `claude` subprocess for all topics, and attempt to correlate replies using message IDs.

**Why it's wrong:** `claude` CLI is a REPL, not a multiplexed API. There is no message correlation protocol. Responses from different projects will interleave.

**Do this instead:** One subprocess per topic, period. The subprocess count is bounded by the number of active projects, which is small (< 10 for the target use case).

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| handlers.py → route() | Direct async call — add `session_ctx` parameter | Only answer/draft/retrieval intents use it |
| route() → PromptBuilder | Direct async call before generation | Returns a str |
| route() → ContextBudgetManager | Direct async call after PromptBuilder | Returns ContextPacket |
| ContextBudgetManager → planning layer | Direct async call to list_tasks() | Cap at 5 most urgent |
| ContextBudgetManager → memory layer | Direct async call to retrieve_context() | Relevance-filtered, not full dump |
| ContextBudgetManager → storage layer | Direct read of message_log | Recent turns only |
| handlers.py → ClaudeSessionManager | Direct async call for Goal 2 path | Branched on chat_id |
| ClaudeSessionManager → filesystem | Direct path operations | One dir per project |
| ClaudeSessionManager → claude CLI | asyncio subprocess (stdin/stdout) | One process per topic |

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Ollama (Qwen3:4b) | HTTP POST to `/api/generate` | Existing, unchanged |
| `claude` CLI | asyncio.create_subprocess_exec | Goal 2 only; uses OAuth session from ~/.claude |
| Telegram Bot API | python-telegram-bot polling | Existing, add thread_id routing for Goal 2 |
| SQLite | aiosqlite async queries | Existing, add 2 new tables for personality |

## Scaling Considerations

This system serves exactly 2 users on a Hetzner CX33 (4 vCPU, 8GB). Scaling is not a concern. The relevant constraints are:

| Concern | Constraint | Mitigation |
|---------|------------|------------|
| 8k context window | Hard limit on Qwen3:4b | Context budget manager is mandatory |
| RAM (8GB shared) | Ollama + 2 bot processes + Claude subprocesses | Claude CLI processes use ~50-100MB each; cap active sessions |
| SQLite contention | 2 bots share one server but each has isolated DB | No contention — isolated DB per deployment |
| subprocess leaks | Claude processes left running | Session manager must handle SIGTERM and idle timeout |

## Sources

- Direct codebase analysis: `app/bot/router.py`, `app/llm/prompts.py`, `app/llm/response_builder.py`, `app/llm/ollama_client.py`, `app/storage/models.py`, `app/bot/handlers.py`
- Project requirements: `.planning/PROJECT.md`
- Existing architecture map: `.planning/codebase/ARCHITECTURE.md`
- Confidence: HIGH — all findings are from first-party source code, not external research

---
*Architecture research for: Tintu adaptive personality + context budget + multi-session Claude CLI*
*Researched: 2026-03-27*
