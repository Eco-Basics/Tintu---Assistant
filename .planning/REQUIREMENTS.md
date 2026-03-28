# Requirements: Tintu — Adaptive Personality Layer

**Defined:** 2026-03-28
**Core Value:** Each user gets an assistant that genuinely adapts to them — remembering preferences, speaking in a shaped style, staying within honest capabilities.

## v1 Requirements

Requirements for this milestone. All map to roadmap phases.

### Foundation

- [ ] **FOUND-01**: System refuses code, math, and research requests before generation via pre-generation keyword check — no hallucinated answers
- [ ] **FOUND-02**: Database schema is extended with additive migrations for personality_traits, behavior_preferences, personas, conversation_summaries tables — no data loss to existing rows

### Personality Layer (PromptBuilder)

- [ ] **PERS-01**: System assembles the Ollama system prompt dynamically from personality_traits and behavior_preferences tables on each request — stored preferences are reflected in every answer
- [ ] **PERS-02**: Rolling conversation history (last 5–8 turns) is included in each Ollama call — assistant can hold a topic across multiple exchanges without the user repeating themselves
- [ ] **PERS-03**: After ~20 turns, session is compressed and stored with a narrative summary and verbatim key_facts column — specific decisions and named entities survive summarization
- [ ] **PERS-04**: When a preference is saved, assistant echoes confirmation ("Saved: I'll be more direct with you") — user can verify capture without querying the database

### Context Budget Management

- [ ] **CTX-01**: A ContextBudgetManager enforces hard per-slot token limits (system prompt, history, retrieved memory, active tasks) — total context stays within 8k window regardless of session length
- [ ] **CTX-02**: Up to 5 most urgent/recent active tasks are injected into each answer via the context budget slot — assistant is aware of current work without the user restating it
- [ ] **CTX-03**: On the first message of a new session, assistant signals whether prior session summary is available — user is never silently surprised by a context reset

## v1.x Requirements

Add after v1 base is validated in real use.

### Differentiators

- **DIFF-01**: User can invoke a named persona for a session ("act like a brutally honest advisor") — session-scoped, does not overwrite base personality
- **DIFF-02**: Before persisting a preference, system makes a second Qwen call to confirm intent ("did the user mean this as a persistent setting?") — prevents casual statements from polluting personality_traits
- **DIFF-03**: Capability refusal message includes a routing hint toward the right tool ("I can't debug this, but I can note it as a task") — refusal is not a dead end
- **DIFF-04**: On SIGTERM, all Claude subprocess handles are cleanly terminated before process exit — no subprocess leak on systemd restart

## Out of Scope

| Feature | Reason |
|---------|--------|
| Goal 2 — Multi-session Claude via Telegram Topics | Out of scope for this run. Architecturally independent. Build after Goal 1 is validated in real use. |
| Fallback to a more capable model | No API access. Clean refusal is the design. Explicitly excluded in PROJECT.md. |
| Web dashboard | Deferred until Telegram UX is proven. Option B per PROJECT.md. |
| Mode system / model routing | Over-engineered for two users with one model. Intent router already dispatches. |
| Automatic memory pruning | Explicit forgetting ("forget that I prefer X") is safer. Auto-purge creates unpredictable drift. |
| Per-message response streaming | Telegram message editing loop adds complexity for marginal UX gain. |
| Multi-user support per bot | Each deployment serves exactly one Telegram user ID. |

## Traceability

Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | — | Pending |
| FOUND-02 | — | Pending |
| PERS-01 | — | Pending |
| PERS-02 | — | Pending |
| PERS-03 | — | Pending |
| PERS-04 | — | Pending |
| CTX-01 | — | Pending |
| CTX-02 | — | Pending |
| CTX-03 | — | Pending |

**Coverage:**
- v1 requirements: 9 total
- Mapped to phases: 0
- Unmapped: 9 ⚠️ (pending roadmap)

---
*Requirements defined: 2026-03-28*
*Last updated: 2026-03-28 after initial definition*
