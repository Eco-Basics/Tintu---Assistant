# Feature Research

**Domain:** Adaptive personal AI assistant — persistent personality, context management, multi-session CLI orchestration
**Researched:** 2026-03-27
**Confidence:** MEDIUM (production competitor analysis from training knowledge, cutoff August 2025; web search unavailable; core project analysis is HIGH from direct codebase and PROJECT.md)

---

## Research Notes

External search tools were unavailable for this session. Competitor analysis (ChatGPT memory, Claude Projects, Notion AI, Character.ai) is drawn from training knowledge (cutoff August 2025) and marked with confidence levels. Project-specific feature analysis is HIGH confidence from direct codebase review and PROJECT.md.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Personality persists across sessions | Users who shaped the assistant's tone expect it to remember how they want to be spoken to; without this, every session resets to a generic assistant that ignores all past shaping | MEDIUM | Core Goal 1. Requires dynamic system prompt from DB. Already has `preferences` table and `update_preference` intent — the missing piece is assembly + injection into `generate()`. |
| Preferences can be set in natural language | Users won't use commands or forms; "be more direct with me" must work | LOW | Already has `update_preference` intent and `PREFERENCE_EXTRACT_PROMPT`. The new need is persisting detected personality signals (tone, style) from the extracted key/value. |
| Behavior preferences are respected immediately | After "skip the confirmation step", the assistant should behave differently in the very next message | MEDIUM | Requires PromptBuilder cache invalidation on `update_preference`. The assembled system prompt must be rebuilt when preferences change, not on TTL. |
| Honest capability boundaries | If the assistant can't do something (code, math, real-time data), it says so clearly and immediately — no confident wrong answer | MEDIUM | Qwen3:4b hallucinates code and math. The refusal must be a pre-generation keyword check, not post-processing. Covered in PITFALLS.md Pitfall 6. |
| Conversation history within a session | The assistant remembers what was said 5 messages ago in the same session without the user repeating it | MEDIUM | Currently absent — Ollama is called with no history. Context budget manager must include rolling last-N-turns slot. This is the most user-visible gap. |
| Named entity recall ("remember what I decided about X") | User expects the assistant to retrieve specific past decisions/facts, not just say "I recall we discussed that topic" | HIGH | Covered in PITFALLS.md Pitfall 3 — Qwen3:4b summaries lose specifics. Requires structured `key_facts` column in `conversation_summaries` and separate retrieval query. |
| Session continuity signal | On first message of a new session, user should know whether the assistant has loaded prior context or is starting fresh | LOW | One-sentence acknowledgment: "I have a summary of our last session available." Prevents the uncanny valley of an assistant that seems to forget everything between sessions with no explanation. |
| Multi-topic Claude sessions don't bleed | If two projects are open in Telegram topics, messages and context stay in their own lane | HIGH | Covered in PITFALLS.md Pitfall 5. Session key must be `(chat_id, message_thread_id)`, not `chat_id`. Foundational to Goal 2. |
| New Claude project requires no new bot token | Adding a project = create a Telegram topic and directory. No redeployment, no new token. | MEDIUM | Explicitly in PROJECT.md requirements. Requires the session manager to dynamically spawn processes for new `thread_id` values it hasn't seen before. |

---

### Differentiators (Competitive Advantage)

Features that set this product apart from generic assistants. Not required to launch, but deliver the core value proposition.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Personality shaped by conversation, not settings menus | Most assistants use explicit forms or toggles. This assistant detects "act like a coach" or "be brutal with me" in natural speech and persists it — no UI required | MEDIUM | Requires `PersonalitySignalDetector` step in the `update_preference` intent path. Classifies extracted key/value pairs by signal type (tone, style, persona, behavior) before inserting to `personality_traits` table. |
| Named on-demand personas | User says "act like a brutally honest advisor for this conversation" and the assistant adopts that frame for the session without permanently overwriting their base personality | MEDIUM | Requires `personas` table (nullable active_persona on session context) and PromptBuilder knowing to override base personality when an active persona is set. Session-scoped, not persistent by default. |
| Context budget is user-transparent | Most LLM products hide context limits. This assistant tells the user when a session is being summarized and what that means for recall. No mystery amnesia. | LOW | UX behavior on top of the context budget manager. No new code — just the right user-facing messaging at two moments: compression trigger and session start. See PITFALLS.md UX Pitfalls. |
| Capability refusal with forward direction | "I can't debug this code, but I can note it as a task for your Claude session in the Projects group." Refusal is not a dead end — it routes the user toward the right tool. | LOW | Canned refusal strings with optional task-capture prompt. Builds trust that the assistant knows its limits. Requires pre-generation keyword classifier (same code as table stakes honest-limits, but with richer refusal message). |
| Active tasks injected into every answer | The assistant knows what you're working on right now. Answers are contextually aware of current projects without the user restating them. | MEDIUM | Cap at 5 most urgent/recent tasks. Slot in ContextPacket. Differentiating because most chat assistants have no awareness of the user's ongoing work unless the user pastes it in. |
| Session summarization without amnesia | After ~20 turns, the session compresses — but key decisions, task titles, and named entities are preserved verbatim in a structured `key_facts` column. Future retrieval can reconstruct specifics, not just vibes. | HIGH | Addresses the core weakness of small-model summarization (Qwen3:4b loses specifics). Two-part summary: narrative paragraph + verbatim key-facts list. Separate `named_entities` column for project names and people. Covered in PITFALLS.md Pitfall 3. |
| Each Claude project has a named working directory | Claude session for "Project Athena" has a persistent directory with its own history. Claude Code in that directory has full file context. Projects don't forget between sessions. | MEDIUM | `~/.claude/` handles Claude's own session state. The session manager's job is ensuring the right `cwd` is passed at spawn time. Low engineering risk, high user value. |
| Preference confidence gating | Not every statement that sounds like a preference is stored. "I usually wake up at 7" doesn't become a persistent trait. Only explicit, high-confidence preferences make it into the system prompt. | MEDIUM | Requires a second Qwen3:4b call or a stricter prompt: "Did the user intend this as a persistent setting?" Adds ~200ms latency on preference-like messages. Covered in PITFALLS.md Pitfall 7. |

---

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems for this specific system.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Fallback to a better model when Qwen can't answer | Users want the assistant to "just figure it out" regardless of question type | Adds Anthropic API dependency and cost; more importantly, confident wrong answers from a small model routed to a larger model is not the same as honest capability limits — it just moves the hallucination. PROJECT.md explicitly out-of-scopes this. | Pre-generation capability refusal that explains what the user should use instead (Claude via Goal 2 for code, for example). |
| Full conversation history in system prompt | Developers assume more context = better answers | System prompt is for persistent instructions, not episodic memory. Mixing them makes token counting ambiguous and confuses the model about what is instruction vs. memory. PITFALLS.md Anti-Pattern 2. | Structured `ContextPacket` with separate slots: system (personality), history (rolling turns), memory (retrieved), tasks (active). |
| Inject all preferences verbatim into every prompt | Simple to implement, guarantees preferences are "always there" | Prompt grows unboundedly after months of use. Low-quality inferred preferences dilute high-signal ones. PITFALLS.md performance trap. | Cap at top 10 most recent/highest-confidence preferences. Token slot limit enforced by ContextBudgetManager. |
| One Claude subprocess for all topics with message correlation | Fewer processes, simpler code | `claude` CLI is a REPL, not a multiplexed API. No correlation protocol exists. Responses from different projects interleave. PITFALLS.md Anti-Pattern 4 and Pitfall 4. | One subprocess per topic, bounded by a hard cap (4 concurrent). |
| Web search for the Qwen assistant | Users expect their assistant to know current information | No API key, no external access. Any answer using web search would require an external service the system is explicitly designed not to have. Attempting it via scraping creates maintenance burden and unreliable results. | Clean refusal: "I don't have internet access, but I can help you note this as a research task." |
| Personality traits editable via a settings UI | Power-users want explicit control | This system's value is that personality emerges from conversation, not configuration. A settings UI creates two competing authoring paths and raises the question of which one wins. It also implies building a web interface (deferred per PROJECT.md). | Conversational preference shaping remains the only path. Viewing current preferences: a `/preferences` command that lists stored traits in Telegram. |
| Mode system or explicit model routing | Seems like a clean way to handle different query types | Over-engineered for two users with one model. The intent router already dispatches to specialized handlers. Adding a "mode" layer on top duplicates routing logic. Explicitly out-of-scope in PROJECT.md. | Intent router + pre-generation capability check covers all cases without modes. |
| Per-message streaming (token-by-token output) | Feels more responsive | `python-telegram-bot` can simulate typing indicators. True streaming requires holding the Telegram message open and editing it repeatedly — creates rate limit risk and message edit conflicts on slow Qwen responses. | Send complete response. Use `bot.send_chat_action(ChatAction.TYPING)` to show typing indicator while Qwen generates. |
| Automatic memory deletion / forgetting | GDPR-friendly, privacy-respecting | Unimplemented forgetting causes unpredictable personality drift and confuses the user ("I told it to forget that but it still acts like it knows"). | Explicit forget intent ("forget that I prefer X") that deletes the specific row and logs the deletion. No auto-purge. |

---

## Feature Dependencies

```
[Conversation History in Session]
    └──requires──> [Context Budget Manager]
                       └──requires──> [Dynamic System Prompt (PromptBuilder)]

[Named Personas]
    └──requires──> [Dynamic System Prompt (PromptBuilder)]
                       └──requires──> [personality_traits + personas DB tables]

[Session Continuity Signal]
    └──requires──> [Session Summarization]
                       └──requires──> [Context Budget Manager]
                                          └──requires──> [Dynamic System Prompt]

[Active Tasks in Answers]
    └──requires──> [Context Budget Manager]
    └──requires──> [existing planning layer (list_tasks)]

[Structured Key-Facts Summarization]
    └──requires──> [Session Summarization trigger in Context Budget Manager]
    └──enhances──> [Named Entity Recall]

[Multi-Topic Claude Sessions]
    └──requires──> [Process Registry (one subprocess per topic)]
    └──requires──> [Telegram Forum/Topics mode configured]

[Preference Confidence Gating]
    └──enhances──> [Personality Persists Across Sessions]
    └──conflicts──> [Inject All Preferences Verbatim] (anti-feature)

[Capability Refusal with Forward Direction]
    └──enhances──> [Honest Capability Boundaries] (table stakes)
    └──enhances──> [Multi-Topic Claude Sessions] (provides a natural routing path for refused tasks)
```

### Dependency Notes

- **Context Budget Manager requires Dynamic System Prompt first:** The budget manager needs the assembled system prompt to calculate remaining token headroom for other slots. PromptBuilder must be complete before the budget manager can be tested end-to-end. Build order: PromptBuilder → ContextBudgetManager → everything downstream.

- **Session Summarization requires Context Budget Manager:** The turn count threshold is tracked inside the budget manager. Summarization trigger fires from `ContextBudgetManager.assemble()`. They are the same implementation phase.

- **Goal 2 (subprocess manager) is independent of Goal 1 (personality layer):** No shared state at runtime. Can be built in parallel or after. The only shared component is `handlers.py` where the branch lives — that branch is a 3-line addition.

- **Personality Confidence Gating enhances but does not block table-stakes delivery:** A simpler implementation (no confidence gate, explicit confirmation echo) satisfies table stakes. The confidence gate is a differentiator that prevents preference noise. Build the simpler version first.

- **Capability Refusal with Forward Direction depends on having the Claude group configured:** The refusal message can say "use your Claude session" only if Goal 2 is live. Until then, the refusal says "note this as a task" or simply states the limitation. The refusal code should not hard-depend on Goal 2 being operational.

---

## How Production Assistants Handle This

**Confidence: MEDIUM — from training knowledge, cutoff August 2025. No live verification possible this session.**

### ChatGPT Memory (OpenAI)

The relevant pattern is: explicit memory notes stored as discrete facts ("User prefers bullet-point responses"), surfaced in a "Memory" panel, injectable into any conversation. Users can view, edit, and delete individual memory items. The model writes memories proactively — the user doesn't have to ask. Two failure modes observed in practice: (1) memories accumulate irrelevant facts from casual statements, diluting signal; (2) users don't trust what's been stored without visibility. **Lesson for Tintu:** The preference-confidence gate (PITFALLS.md Pitfall 7) directly addresses failure mode 1. The "echo back what was saved" behavior addresses failure mode 2.

### Claude Projects (Anthropic)

Project Instructions serve as a persistent system prompt scoped to a project. Users write instructions in natural language. The separator between "instructions" and "conversation" is explicit — there is a designated instructions field, not automatic extraction. Knowledge documents can be uploaded and are retrieved per query. **Lesson for Tintu:** The personality layer is similar to Project Instructions but auto-assembled from DB rather than a static text field. The key differentiator here is that Tintu's personality _evolves_ through conversation rather than requiring the user to write instructions. This is the core value difference worth preserving.

### Notion AI

Relevant pattern: Notion AI operates on workspace context (existing documents, database entries) rather than conversation history. It has strong "what exists" awareness but weak "what you've told me" memory. **Lesson for Tintu:** The `Obsidian vault + SQLite` combo gives Tintu something Notion AI lacks — structured episodic memory (tasks, decisions, summaries) alongside document context. The retrieval layer should query both. This is already in the existing architecture; the personality layer should not compete with or duplicate it.

### Context Window Management at Product Level

The most consistent UX pattern across production assistants is: **users don't want to think about context windows, but they do want to know when something was forgotten.** ChatGPT's memory panel, Claude's project knowledge, and Notion AI's document scope all solve this differently — but all of them provide some form of "here's what I know about you" visibility. The failure case all products share: silent forgetting with no signal to the user. **Lesson for Tintu:** The session continuity signal ("Starting fresh — I have a summary of our last session available") directly addresses this. It is low-complexity and high-trust.

### Multi-Session CLI Tooling (Claude Code patterns)

The expected UX for parallel Claude Code sessions: each session is a separate context — no bleed between them, each has its own cwd, each maintains its own CLAUDE.md and history. The separation is enforced by directory, not by process IDs. **Lesson for Tintu (Goal 2):** The Telegram Topics approach maps cleanly to this model. Topic = project directory = Claude process. The user's mental model is "each topic is a separate Claude for that project." The implementation must enforce this absolutely — one topic, one process, one directory, no exceptions.

---

## MVP Definition

### Launch With (v1 — Goal 1)

Minimum viable personality + context layer. Validates that the core value ("assistant that adapts to you") is perceptible to the user.

- [ ] **Dynamic system prompt from preferences table** — the most visible change; users who have set preferences will see them respected in every answer. Without this, the entire personality layer has no effect.
- [ ] **Conversation history in ContextPacket (last ~5-8 turns)** — without this, every Ollama call is stateless and the assistant cannot hold a topic for more than one exchange. Users notice this immediately.
- [ ] **Capability refusal (pre-generation keyword check)** — must ship before personality testing to prevent Qwen hallucinating code/math responses that erode trust.
- [ ] **Session summarization (trigger + key-facts storage)** — required to prevent context bloat from making the assistant worse over time, and to enable recall of prior sessions.
- [ ] **Preference echo-back ("Saved: I'll...")** — low cost, high trust signal. Without this, users can't verify preferences were captured.

### Add After Validation (v1.x — still Goal 1)

Add once core personality layer is working and user-tested by Mithu.

- [ ] **Named persona support** — trigger: user explicitly requests a different persona and finds the lack of it limiting. Don't add before the base personality is working well.
- [ ] **Preference confidence gating** — trigger: `preferences` table starts accumulating noise rows from casual conversation. Add the confidence gate once the problem is visible.
- [ ] **Active tasks in ContextPacket** — trigger: user mentions that answers feel disconnected from their current work. The planning layer already has `list_tasks()` — this is a small addition to the budget manager.
- [ ] **Session continuity signal** — trigger: user is confused about what the assistant remembers between sessions. Low complexity, add it as soon as session summarization is working.

### Launch With (v1 — Goal 2)

Minimum viable multi-session Claude access via Telegram Topics.

- [ ] **Process registry (one subprocess per topic)** — foundational; nothing else works without it.
- [ ] **Telegram Forum/Topics routing with `(chat_id, message_thread_id)` key** — must be correct before any message routing is tested.
- [ ] **Spawn-on-demand for new topics** — a new Telegram topic automatically gets a Claude process on first message; no manual config.
- [ ] **Graceful shutdown (SIGTERM cleans up subprocesses)** — required before VPS deployment; prevents subprocess leak on systemd restart.
- [ ] **Hard cap at 4 concurrent Claude processes** — RAM guard. At 50-100MB per `claude` process, 4 processes = 200-400MB peak, within CX33 headroom alongside Ollama.

### Future Consideration (v2+)

Defer until both goals are working and used daily for 4+ weeks.

- [ ] **Web dashboard (Option B)** — explicitly deferred in PROJECT.md until Option A (Telegram) is proven. Add only if the Telegram UX creates friction that a dashboard would solve.
- [ ] **Streaming responses for Goal 2** — nice-to-have for long Claude responses. Requires Telegram message editing loop. Adds complexity for marginal UX gain given typical response latency.
- [ ] **Multi-user support per bot** — out of scope per PROJECT.md; design is single-user-per-deployment.
- [ ] **Automatic memory pruning** — defer indefinitely. See anti-features. Explicit forgetting is safer.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Dynamic system prompt from preferences | HIGH | MEDIUM | P1 |
| Conversation history in ContextPacket | HIGH | MEDIUM | P1 |
| Capability refusal (keyword pre-check) | HIGH | LOW | P1 |
| Session summarization (trigger + key-facts) | HIGH | HIGH | P1 |
| Preference echo-back | MEDIUM | LOW | P1 |
| Process registry (Goal 2) | HIGH | MEDIUM | P1 |
| Telegram topic routing correctness | HIGH | LOW | P1 |
| Graceful subprocess shutdown | HIGH | LOW | P1 |
| Active tasks in ContextPacket | HIGH | LOW | P2 |
| Session continuity signal (UX message) | MEDIUM | LOW | P2 |
| Preference confidence gating | MEDIUM | MEDIUM | P2 |
| Named persona support | MEDIUM | MEDIUM | P2 |
| Capability refusal with forward direction | MEDIUM | LOW | P2 |
| Hard cap on concurrent Claude processes | MEDIUM | LOW | P2 |
| Streaming Goal 2 responses | LOW | HIGH | P3 |
| Web dashboard | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

**Confidence: MEDIUM — training knowledge, August 2025 cutoff.**

| Feature | ChatGPT Memory | Claude Projects | Tintu Approach |
|---------|----------------|-----------------|----------------|
| Persistent personality | Discrete facts extracted automatically; user can view/delete | Static Project Instructions field; user writes them explicitly | Auto-extracted from conversation via `update_preference` intent; assembled dynamically each request |
| User control over what's stored | View and delete individual memories | Edit the instructions field directly | Echo-back + explicit forget intent; confidence gating prevents noise |
| Context window signal to user | None (silent truncation) | None | Session continuity message on first turn of new session; compression is announced |
| Named personas | No native support | Users can write persona into project instructions manually | Named personas table; session-scoped activation via natural language |
| Active work awareness | No native task/project injection | Project knowledge documents (static) | Active tasks injected from planning layer (dynamic, up to 5) |
| Multi-session isolation | Separate chat threads (no project working directory concept) | Separate projects (static docs, not process isolation) | Separate Telegram topics with one-process-per-topic; Claude's own directory-based context |
| Capability limits | Soft (ChatGPT tries everything, quality degrades) | Soft (Claude tries everything) | Hard pre-generation refusal for code/math/research; honest about ceiling |

---

## Sources

- Direct codebase analysis: `.planning/PROJECT.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md`
- ChatGPT memory behavior: training knowledge (OpenAI launched memory in ChatGPT, ~2024; behavior as of August 2025 cutoff) — MEDIUM confidence
- Claude Projects: training knowledge (Anthropic launched Projects ~late 2024; behavior as of August 2025 cutoff) — MEDIUM confidence
- Notion AI: training knowledge (Notion AI workspace context patterns) — MEDIUM confidence
- Claude Code multi-session patterns: training knowledge (Claude Code CLI directory-based context isolation) — MEDIUM confidence
- Note: All external competitor claims require verification if used as requirements justification. The project-specific recommendations derive from HIGH-confidence first-party sources.

---
*Feature research for: Tintu adaptive AI assistant — persistent personality, context management, multi-session subprocess orchestration*
*Researched: 2026-03-27*
