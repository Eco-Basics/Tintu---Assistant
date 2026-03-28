# Roadmap: Tintu — Adaptive Personality Layer

## Overview

Three phases deliver the complete Goal 1 personality system on top of the existing Telegram bot and Qwen3:4b inference stack. Phase 1 lays safe foundations — capability refusal and database schema — so that personality testing can begin without hallucinated answers polluting user trust. Phase 2 wires the dynamic system prompt into every Ollama call, making stored preferences visible for the first time. Phase 3 completes the context layer: conversation history, session summarization with verbatim key-facts, the 8k-token budget manager, active task injection, and the session continuity signal. When Phase 3 ships, both bots are ready for real use on VPS.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Capability refusal guard and additive DB schema migrations
- [ ] **Phase 2: PromptBuilder** - Dynamic system prompt assembled from preferences DB on every request
- [ ] **Phase 3: Context Budget Manager** - Conversation history, session summarization, 8k token enforcement, active tasks, continuity signal

## Phase Details

### Phase 1: Foundation
**Goal**: Users are protected from hallucinated answers and the database is ready to store personality data
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02
**Success Criteria** (what must be TRUE):
  1. Sending a code, math, or research request to the bot receives a clear refusal message before any Ollama call is made — no hallucinated code or math output ever reaches the user
  2. The SQLite database contains the personality_traits, behavior_preferences, personas, and conversation_summaries tables after migration — verified by schema inspection with no existing rows lost
  3. Both assistant-mithu and assistant-friend bots apply the capability refusal check independently — one bot's configuration does not affect the other
**Plans**: TBD

### Phase 2: PromptBuilder
**Goal**: Every Ollama call uses a system prompt assembled from the user's stored preferences and personality traits — stored personality is reflected in every answer
**Depends on**: Phase 1
**Requirements**: PERS-01, PERS-04
**Success Criteria** (what must be TRUE):
  1. After a user sets a preference (e.g. "be more direct"), the assistant's next response reflects that preference in tone — without the user having to repeat it
  2. After updating a preference, the bot replies with an explicit confirmation ("Saved: I'll be more direct with you") — the user can verify capture without querying the database
  3. A preference set in one session is still active in a new session started after restarting the bot service — personality survives process restarts
  4. The DEBUG log shows the assembled system prompt string on every Ollama call — personality injection is verifiable without a database query
**Plans**: TBD

### Phase 3: Context Budget Manager
**Goal**: The assistant holds multi-turn conversations, remembers specific facts across sessions, stays within the 8k token window, and signals when it starts fresh
**Depends on**: Phase 2
**Requirements**: PERS-02, PERS-03, CTX-01, CTX-02, CTX-03
**Success Criteria** (what must be TRUE):
  1. A user can reference something said 4 exchanges ago and the assistant responds accurately without the user repeating it — rolling conversation history is live
  2. After approximately 20 turns, the session is compressed and stored; a named entity or specific decision mentioned in the session can be retrieved by the assistant in a later session — key facts survive summarization
  3. The assembled context (system prompt + history + tasks + memory + message) never exceeds 8,192 tokens as confirmed by Ollama's prompt_eval_count field — the budget manager enforces the hard limit
  4. At the start of a new session, the assistant explicitly signals whether a prior session summary is available — the user is never silently surprised by a context reset
  5. Up to 5 active tasks are mentioned in the assistant's responses when relevant — the assistant is aware of current work without the user restating it
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/TBD | Not started | - |
| 2. PromptBuilder | 0/TBD | Not started | - |
| 3. Context Budget Manager | 0/TBD | Not started | - |
