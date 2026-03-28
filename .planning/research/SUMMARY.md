# Project Research Summary

**Project:** Tintu — Personal AI Assistant Platform
**Domain:** Adaptive personal AI assistant with persistent personality, context management, and multi-session Claude CLI orchestration via Telegram
**Researched:** 2026-03-28
**Confidence:** HIGH (stack and architecture from direct codebase analysis; features and pitfalls from first-party source code + domain knowledge)

## Executive Summary

Tintu is a two-goal project built on an already-sound existing codebase. Goal 1 adds a personality layer to a Qwen3:4b-powered Telegram bot: preferences and personality signals extracted from conversation are persisted to SQLite and assembled into a dynamic system prompt on every request, replacing the current hardcoded static string. Goal 2 adds a separate Telegram group in Forum/Topics mode where each topic maps to a persistent Claude CLI session, enabling multi-session Claude Code access without additional bot tokens or redeployment. Both goals operate on a Hetzner CX33 (4 vCPU, 8GB RAM) running two Python bot processes, one Ollama instance, and spawned Claude CLI subprocesses.

The recommended approach is to build in strict dependency order: PromptBuilder first (reads preferences, assembles dynamic system prompt), then ContextBudgetManager (enforces token slots, triggers summarization, adds conversation history), then Goal 2's ClaudeSessionManager in parallel or after. The existing stack — `python-telegram-bot 21.3`, `httpx`, `aiosqlite`, `python-dotenv` — requires only one addition (`tiktoken`) for Goal 1. Goal 2 requires no new libraries; `asyncio.create_subprocess_exec` with `--output-format json` and `--resume` is the correct subprocess pattern.

The highest-severity risks are: (1) context overflow via silent Ollama truncation — mitigated by explicit `num_ctx=8192` in every Ollama payload and checking `prompt_eval_count` in responses; (2) Claude subprocess leaks causing OOM on the shared VPS — mitigated by a process registry with a hard cap of 4 concurrent processes and SIGTERM cleanup; (3) session summarization losing specific facts at Qwen3:4b's capability level — mitigated by a two-part summary structure with a verbatim `key_facts` column separate from the narrative. All three risks have concrete, low-overhead mitigations that must be in place before user-facing testing begins.

## Key Findings

### Recommended Stack

The existing stack is correct and requires no replacements. One library addition is needed. `tiktoken` (or Qwen3:4b's Hugging Face tokenizer via `transformers.AutoTokenizer`) is required for accurate token counting in the context budget manager — the common `len(text) / 4` heuristic systematically undercounts CJK characters and structured text, leading to silent context overflow. Goal 2 uses only Python's stdlib `asyncio` for subprocess management.

Ollama must be configured with `OLLAMA_NUM_PARALLEL=1` and `OLLAMA_MAX_LOADED_MODELS=1` in a systemd override to prevent memory overrun on the 8GB VPS. The estimated memory budget leaves ~3.3GB headroom under normal operation. The two bot databases are completely isolated (separate files, separate paths) — no SQLite contention exists between bots.

**Core technologies:**
- `python-telegram-bot[job-queue]==21.3`: Telegram bot framework — async-native, correct version, no replacement needed
- `httpx==0.27.0`: Ollama HTTP client — keep as-is, aiohttp migration has no benefit at this message volume
- `aiosqlite==0.20.0`: Async SQLite — WAL mode already enabled in `db.py`, isolated DB per bot
- `tiktoken>=0.7.0`: Token counting for context budget — only new dependency, needed for Goal 1
- `asyncio.create_subprocess_exec`: Claude CLI subprocess management — stdlib, no new packages for Goal 2
- Ollama + Qwen3:4b Q4_K_M: Local inference, ~3.5GB RAM at runtime, fits 8GB VPS with headroom
- systemd: Service lifecycle — existing service files correct, add `MemoryMax=512M` resource limits

### Expected Features

**Must have (table stakes — Goal 1):**
- Dynamic system prompt assembled from preferences DB — without this, the entire personality layer has no effect
- Conversation history in ContextPacket (last 5-8 turns) — currently absent; Ollama is called stateless; users notice immediately
- Capability refusal (pre-generation keyword check before any LLM call) — must ship before personality testing to prevent Qwen hallucinating code/math
- Session summarization with verbatim key-facts storage — prevents context bloat and enables specific-fact recall
- Preference echo-back after capture ("Saved: I'll...") — low cost, high trust signal

**Must have (table stakes — Goal 2):**
- Process registry mapping `(chat_id, message_thread_id)` to one Claude subprocess per topic — foundational, nothing else works without it
- Spawn-on-demand for new topics — new Telegram topic gets a Claude process on first message, no manual config
- Hard cap at 4 concurrent Claude processes — RAM guard before VPS deployment
- Graceful SIGTERM shutdown cleaning up all subprocesses — required before any VPS deployment

**Should have (differentiators, add after validation):**
- Named persona support — session-scoped persona overrides without permanent personality change
- Preference confidence gating — prevents casual conversational statements from polluting the preferences table
- Active tasks injected into every ContextPacket — contextual awareness of current work without user restating it
- Session continuity signal on first message of new session — eliminates "mystery amnesia" UX failure
- Capability refusal with forward routing ("note as task for Claude session") — refusal is not a dead end

**Defer (v2+):**
- Web dashboard (Option B) — explicitly deferred in PROJECT.md until Telegram UX is proven
- Streaming Goal 2 responses — marginal UX gain, adds Telegram rate-limit risk
- Multi-user support per bot — out of scope per PROJECT.md

### Architecture Approach

The architecture adds three new components into the existing system, each with clear boundaries. Goal 1 intercepts the `route() → build_answer() → generate()` path: PromptBuilder assembles a dynamic system prompt from DB before generation; ContextBudgetManager enforces token slots across system prompt, history, tasks, memory, and message, and triggers session summarization at ~20 turns. Goal 2 branches at the top of `handlers.py` — if `chat_id == CLAUDE_GROUP_ID`, messages go to ClaudeSessionManager instead of the intent router. The two goals share no runtime state.

**Major components:**
1. `app/llm/prompt_builder.py` (NEW) — reads `preferences`, `personality_traits`, `personas` tables; assembles dynamic system prompt string; cached with invalidation on `update_preference`
2. `app/llm/context_budget.py` (NEW) — enforces 8k token window across 5 named slots; triggers `summarize_session()` at 20-turn threshold; returns immutable `ContextPacket` dataclass to `generate()`
3. `app/claude/session_manager.py` (NEW) — manages dict of `thread_id → subprocess`; spawn-on-demand; hard cap via `asyncio.Semaphore(4)`; SIGTERM handler; health-check job
4. `app/storage/models.py` (EXTEND) — add `personality_traits` and `personas` tables; add `key_facts` and `named_entities` columns to `conversation_summaries`

Key patterns: Context Packet is assembled once, immutably, before `generate()` — never manipulated inside the router or generation path. Extraction intents (`create_task`, `set_reminder`, `update_preference`, etc.) receive only their extraction prompt, not the full context packet — injecting personality into extraction prompts degrades structured output reliability.

### Critical Pitfalls

1. **Personality stored but never injected** — the assembler must log the assembled system prompt at DEBUG level on every call; add a unit test asserting DB rows appear in the assembled string; allocate a guaranteed minimum token slot (200 tokens) for personality before any other slot
2. **Silent Ollama context overflow** — always pass `"options": {"num_ctx": 8192}` in the Ollama payload; check `prompt_eval_count` in every response body; log an alert if assembled token count exceeds 7,500; never use `len(text) / 4` for token estimation in production
3. **Subprocess leaks causing VPS OOM** — process registry with `poll()` liveness check must exist before any subprocess is created; wrap all subprocess I/O in try/finally with timeout; health-check job every 5 minutes; SIGTERM handler iterates registry and terminates all processes
4. **Topic routing collision** — session key must always be `(chat_id, message_thread_id)` tuple, never `chat_id` alone; add startup assertion that rejects routing if `message_thread_id is None` in a group context; test with Forum mode explicitly enabled
5. **Preference noise overwrite** — add confidence gate (second Qwen call: "did user intend this as persistent?") or explicit confirmation echo before writing; add `confidence` column to `preferences` table; only inject high/medium confidence preferences into system prompt

## Implications for Roadmap

Based on the dependency graph established in ARCHITECTURE.md and FEATURES.md, and the pitfall-to-phase mapping in PITFALLS.md, the following phase structure is strongly recommended.

### Phase 1: Foundation — Capability Refusal and DB Schema

**Rationale:** Capability refusal must be in place before any personality testing begins. A pre-generation keyword check requires no new components and prevents Qwen3:4b hallucinations from eroding user trust during later testing. The DB schema additions (`personality_traits`, `personas`, `key_facts` column) are required by every subsequent phase and have zero risk — they are additive migrations.
**Delivers:** Pre-generation capability refusal; `personality_traits` and `personas` tables; `key_facts` / `named_entities` columns in `conversation_summaries`; systemd resource limits on existing service files
**Addresses:** Table-stakes "honest capability limits"; foundation for all Goal 1 features
**Avoids:** Pitfall 6 (Qwen capability hallucination reaching users before guardrails exist)
**Research flag:** No research needed — capability keyword patterns are well-defined; schema migrations are standard

### Phase 2: Goal 1A — Dynamic System Prompt (PromptBuilder)

**Rationale:** PromptBuilder has no dependencies on other new components. It reads the existing `preferences` table and the new `personality_traits` table. It is the first piece of the personality layer that a user can observe. Must be complete before ContextBudgetManager, which depends on the assembled system prompt to calculate remaining token headroom.
**Delivers:** `app/llm/prompt_builder.py`; wired into `build_answer()` and `build_retrieval_answer()`; in-memory cache with invalidation on `update_preference` intent; preference echo-back UX
**Addresses:** "Personality persists across sessions" (table stakes); "Preferences respected immediately" (table stakes); "Preference echo-back" (trust signal)
**Avoids:** Pitfall 1 (personality stored but never injected); Anti-Pattern 1 (formatting static SYSTEM_PROMPT at call sites)
**Research flag:** No research needed — standard DB-to-string assembly pattern, verified against existing codebase

### Phase 3: Goal 1B — Context Budget Manager

**Rationale:** Depends on PromptBuilder (Phase 2) being complete. This phase adds conversation history to every Ollama call — the most user-visible gap in the current system. It also adds the session summarization trigger and implements the two-part summary structure (narrative + verbatim key-facts) that prevents Qwen3:4b from paraphrasing specifics into vagueness.
**Delivers:** `app/llm/context_budget.py`; `ContextPacket` dataclass; rolling last-8-turns history slot; 20-turn summarization trigger; structured summary with `key_facts` and `named_entities`; active-tasks slot (P2 feature, low cost to include here); `SUMMARIZE_SESSION_PROMPT` in `prompts.py`; session continuity signal on first message of new session
**Addresses:** "Conversation history in session" (table stakes); "Named entity recall" (table stakes); "Session summarization without amnesia" (differentiator); "Active tasks in every answer" (differentiator); "Session continuity signal" (differentiator)
**Avoids:** Pitfall 2 (silent context overflow); Pitfall 3 (summarization losing specifics); Anti-Pattern 2 (full history in system prompt)
**Research flag:** Token counting approach needs one decision: `tiktoken` vs. `transformers.AutoTokenizer` for Qwen3 — recommend `tiktoken` for lower startup overhead; validate token counts match Ollama's `prompt_eval_count` in first integration test

### Phase 4: Goal 1C — Preference Confidence Gating and Persona Support

**Rationale:** These are P2 differentiators that build on the working personality layer from Phases 2-3. The confidence gate adds a second Qwen3:4b call on preference-like messages — add only once the `preferences` table shows noise accumulation in real use. Named personas require the `personas` table (already created in Phase 1) and a minor PromptBuilder extension.
**Delivers:** Confidence gate in `update_preference` path; `confidence` column in `preferences` table; named persona activation via natural language; session-scoped persona override in ContextPacket
**Addresses:** "Preference confidence gating" (differentiator); "Named personas" (differentiator); "Personality shaped by conversation" (differentiator)
**Avoids:** Pitfall 7 (preference noise overwrite)
**Research flag:** No research needed — patterns are fully specified in FEATURES.md and PITFALLS.md; trigger on real-world noise observation

### Phase 5: Goal 2 — Claude CLI Multi-Session Subprocess Manager

**Rationale:** Goal 2 is architecturally independent of Goal 1 — it shares no runtime state and the only shared code is a 3-line branch in `handlers.py`. It can be built after Phase 3, in parallel with Phase 4, or as a standalone track. The process registry must be the first thing built in this phase — no message routing before the registry exists.
**Delivers:** `app/claude/` package; `ClaudeSessionManager` with process registry; spawn-on-demand for new topics; `(chat_id, message_thread_id)` routing key; `asyncio.Semaphore(4)` concurrency cap; SIGTERM cleanup handler; health-check job; `claude_sessions` SQLite table for session ID persistence; third systemd service file
**Addresses:** "Multi-topic Claude sessions don't bleed" (table stakes); "New Claude project requires no new bot token" (table stakes); all Goal 2 MVP requirements from FEATURES.md
**Avoids:** Pitfall 4 (subprocess leaks); Pitfall 5 (topic routing collision); Anti-Pattern 4 (shared subprocess across topics)
**Research flag:** One integration test must be run first: verify Telegram Forum/Topics mode is enabled on the target group and `message_thread_id` is non-null before writing any subprocess code — this is the failure mode that only manifests in production

### Phase Ordering Rationale

- Phase 1 before Phase 2: Capability refusal and schema setup are zero-risk prerequisites with no downward dependencies. Shipping refusal first prevents the worst user-trust failure (confident wrong answers) during personality testing.
- Phase 2 before Phase 3: PromptBuilder output is a required input to ContextBudgetManager's slot calculation. They cannot be integrated in reverse order.
- Phase 3 before Phase 4: The persona and confidence-gate features are built on the working ContextPacket from Phase 3. Testing them without a working context layer produces misleading results.
- Phase 5 is independent: Goal 2 has zero shared state with Goal 1 at runtime. It can run in parallel with Phases 3-4 or after, depending on development capacity.

### Research Flags

Phases requiring deeper research during planning:
- **Phase 3 (Context Budget Manager):** Token counting library decision needs validation against actual Qwen3:4b tokenizer behavior — confirm `tiktoken` approximation stays within 5% of true token count for typical message content; check `prompt_eval_count` in first Ollama response as ground truth

Phases with standard patterns (no research-phase needed):
- **Phase 1:** Additive SQLite migrations and pre-generation keyword filtering — fully specified, no unknowns
- **Phase 2:** DB-to-string prompt assembly with in-memory cache — standard pattern, no external dependencies
- **Phase 4:** Second LLM call for confidence gating — pattern specified in FEATURES.md and PITFALLS.md
- **Phase 5:** `asyncio.create_subprocess_exec` + `--resume` pattern is fully documented in STACK.md with implementation code

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All findings from direct codebase inspection and verified official docs (Ollama FAQ, Python asyncio docs, PTB wiki, Claude CLI headless docs) |
| Features | MEDIUM-HIGH | Project-specific feature analysis is HIGH (first-party sources); competitor analysis (ChatGPT, Claude Projects) is MEDIUM (training knowledge, August 2025 cutoff, unverifiable this session) |
| Architecture | HIGH | Entirely derived from direct source code analysis of `router.py`, `handlers.py`, `ollama_client.py`, `models.py`, `response_builder.py`, `prompts.py` |
| Pitfalls | HIGH | Derived from direct codebase analysis + known LLM context management failure modes; Ollama silent truncation behavior verified against API documentation patterns |

**Overall confidence:** HIGH

### Gaps to Address

- **Token counting accuracy for Qwen3:4b:** `tiktoken` uses a GPT-compatible BPE tokenizer which approximates Qwen3's tokenizer. For ASCII-dominant English text the error is small (<5%). For Tamil, other Indic scripts, or heavily structured content (JSON, code), undercounting risk increases. Mitigation: cross-check assembled prompt token count against `prompt_eval_count` in the first 20 Ollama responses after Phase 3 ships; adjust slot budgets if systematic deviation is observed.
- **Claude CLI output format stability:** The `--output-format json` interface is documented as stable, but `session_id` field naming and response structure may evolve with CLI auto-updates. Mitigation: add a startup smoke test that validates the JSON schema before the service goes live; fail loudly if `session_id` or `result` keys are missing.
- **`communicate()` vs `readline()` for Claude CLI subprocess:** PITFALLS.md flags that `communicate()` waits for EOF while `claude` CLI may not close stdout in interactive mode. STACK.md recommends `communicate()` with the `-p --print` (one-shot) flag, which does exit after printing. Verify empirically on first subprocess integration test that one-shot mode closes stdout cleanly. If not, switch to `readline()` with timeout.
- **Competitor feature analysis currency:** The ChatGPT Memory and Claude Projects analysis is from training knowledge (cutoff August 2025). These products evolve rapidly. The analysis is used only to validate design decisions already made in PROJECT.md, not to drive new requirements — acceptable to proceed without live verification.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: `app/bot/router.py`, `app/llm/prompts.py`, `app/llm/response_builder.py`, `app/llm/ollama_client.py`, `app/storage/models.py`, `app/storage/db.py`, `app/bot/handlers.py`, `app/memory/summarizer.py`, `app/memory/retrieval.py`
- `.planning/PROJECT.md` — constraints, goals, explicit out-of-scopes
- `.planning/codebase/CONCERNS.md` — known fragile areas
- `.planning/codebase/ARCHITECTURE.md` — existing system architecture map
- Ollama FAQ on `OLLAMA_NUM_PARALLEL` and queue behavior: https://docs.ollama.com/faq
- Claude CLI headless/print mode: https://code.claude.com/docs/en/headless
- Claude CLI `--resume` and session IDs: https://code.claude.com/docs/en/headless#continue-conversations
- Python asyncio subprocess docs: https://docs.python.org/3/library/asyncio-subprocess.html
- SQLite WAL mode: https://sqlite.org/wal.html
- systemd resource control: https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html

### Secondary (MEDIUM confidence)
- Ollama parallel request behavior: https://www.glukhov.org/post/2025/05/how-ollama-handles-parallel-requests/
- Ollama GitHub issue on concurrent requests: https://github.com/ollama/ollama/issues/9054
- Claude CLI large stdin issue: https://github.com/anthropics/claude-code/issues/7263
- Qwen3-4B memory requirements: https://apxml.com/models/qwen3-4b
- python-telegram-bot JobQueue / APScheduler: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions---JobQueue

### Tertiary (LOW confidence — training knowledge only)
- ChatGPT Memory feature behavior (as of August 2025) — used for design validation only, not requirements
- Claude Projects feature behavior (as of August 2025) — used for design validation only, not requirements
- Notion AI workspace context patterns — used for design validation only, not requirements

---
*Research completed: 2026-03-28*
*Ready for roadmap: yes*
