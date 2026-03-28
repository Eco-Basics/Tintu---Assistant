# Phase 2: PromptBuilder - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the static `SYSTEM_PROMPT` in `build_answer()` and `draft_reply` with a dynamically assembled system prompt read from the database on every request. Implement the preference confirmation echo (PERS-04). No personality trait detection or context window budget enforcement in this phase — those are Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Prompt assembly — structure and ordering

- Section order: **base identity → behavior preferences → personality traits → active persona**
- Each section is included only if it has content, except personality_traits which always includes a placeholder line ("Personality traits: none yet") even when the table is empty — this keeps the slot visible in DEBUG logs so the section is verifiable
- Base identity is the existing `SYSTEM_PROMPT` string (unchanged content, now the first section)
- Behavior preferences: all rows from the `preferences` table (key/value pairs), formatted as natural language instructions (e.g., "Be more direct.", "Skip confirmation before creating tasks.")
- Personality traits: all rows from `personality_traits` table; if empty, show "Personality traits: none yet"
- Active persona: if any row in `personas` has `is_active=1`, append as additional instruction — "For this session, adopt the following persona: [description]." Base identity remains active; persona supplements it

### Prompt assembly — which calls get the dynamic prompt

- **Gets dynamic prompt:** `build_answer()` and `draft_reply` in `router.py` only
- **Stays on static prompts:** All extraction calls (task, reminder, preference, decision, completion — `TASK_EXTRACT_PROMPT`, `REMINDER_EXTRACT_PROMPT`, `PREFERENCE_EXTRACT_PROMPT`, etc.) — these structured-output calls must not be influenced by personality context
- `build_retrieval_answer()` and `build_compare_answer()` — these use `SYSTEM_PROMPT` today; they should also receive the dynamic prompt since they produce user-facing answers

### Prompt assembly — DEBUG logging

- On every assembled prompt: `logger.debug(f"system_prompt=\n{assembled_prompt}")` — full string, no truncation
- Logged in the module that assembles the prompt (not in `generate()`), so it appears before the Ollama call
- This satisfies PERS-01 success criterion 4: "DEBUG log shows assembled system prompt on every Ollama call"

### Preference confirmation (PERS-04)

- Current response format: `"Preference saved: *{key}* = {value}"` — this must change to natural language echo
- Required format: `"Saved: [natural language restatement of what was captured]"` — e.g., "Saved: I'll be more direct with you" or "Saved: I'll skip confirmation before creating tasks"
- The natural language echo is generated via a lightweight Qwen call or a simple template transform — implementation detail is Claude's discretion
- The confirmation must be explicit enough for the user to verify capture without querying the database

### preferences table — compatibility confirmed

- The existing `preferences` table (key TEXT UNIQUE, value TEXT, source TEXT) is fully compatible with Phase 2's needs
- PromptBuilder reads all rows and formats them as prompt fragments — no schema changes required
- This resolves the [RISK — Phase 2 planning] from STATE.md open risks: no Phase 2.1 migration needed

### Trait detection — out of scope

- `personality_traits` table starts empty after Phase 1 migration
- Phase 2 only reads from `personality_traits` — nothing writes to it in this phase
- Automatic signal detection from natural conversation is a future phase (not in v1 requirements as a mapped REQ-ID)
- PromptBuilder handles the empty case gracefully (shows placeholder line per logging decision above)

### Claude's Discretion

- Exact module location for the PromptBuilder (new file `app/llm/prompt_builder.py` is the natural choice, but planner decides)
- Exact string format for each preferences row in the assembled prompt (natural language transform vs key=value)
- Whether to use a Qwen call or template string for preference confirmation echo — either is acceptable
- Caching strategy for assembled prompt within a single request cycle (not across requests)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs or ADRs — this project has no separate spec documents.

### Requirements
- `.planning/REQUIREMENTS.md` — PERS-01 (prompt assembly from personality_traits + preferences) and PERS-04 (preference confirmation echo) acceptance criteria

### Phase 1 context (upstream decisions)
- `.planning/phases/01-foundation/01-CONTEXT.md` — personality_traits column spec (key, value, signal_type, confidence, source), personas column spec (name, description, is_active), preferences table confirmed as behavior_preferences role

### Live code to read before planning
- `app/llm/response_builder.py` — `build_answer()`, `build_retrieval_answer()`, `build_compare_answer()` — all three need the dynamic prompt
- `app/llm/prompts.py` — `SYSTEM_PROMPT` (current static string, becomes the base identity section)
- `app/bot/router.py` — `draft_reply` block and `update_preference` block (both need changes)
- `app/storage/models.py` — preferences, personality_traits, personas table schemas
- `app/llm/ollama_client.py` — `generate(prompt, system=...)` signature

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `generate(prompt, system=str)` in `app/llm/ollama_client.py` — already accepts a `system` parameter; PromptBuilder just supplies a different string
- `execute()` and `fetchall()` in `app/storage/db.py` — standard async DB helpers; PromptBuilder uses `fetchall()` to read preferences, personality_traits, and personas
- `SYSTEM_PROMPT` in `app/llm/prompts.py` — becomes the base identity section of the assembled prompt; content unchanged

### Established Patterns
- All DB reads use `await fetchall(sql, params)` from `app/storage/db.py` — PromptBuilder follows the same pattern
- Logging uses `logging.getLogger(__name__)` at module level — PromptBuilder follows same pattern

### Integration Points
- `build_answer(message)` → `generate(message, system=SYSTEM_PROMPT)` — change to `generate(message, system=await build_system_prompt())`
- `draft_reply` block in `router.py` → same substitution
- `build_retrieval_answer()` and `build_compare_answer()` → same substitution
- `update_preference` block in `router.py` → change return string from `"Preference saved: *{key}* = {value}"` to natural language echo per PERS-04
- The assembled prompt must be awaited (async DB reads) — callers must use `await`

</code_context>

<specifics>
## Specific Ideas

- The DEBUG log must show the full assembled prompt string — no truncation. This is explicitly required by PERS-01 success criterion 4.
- Persona appended as supplementary instruction, not replacement: "For this session, adopt the following persona: [description]." The base identity tone constraints (concise, structured, not chatty) remain active unless the persona explicitly overrides them.

</specifics>

<deferred>
## Deferred Ideas

- Automatic personality trait detection from natural conversation messages — future phase (not in v1 REQ-IDs)
- Confidence-gated trait persistence (DIFF-02: second Qwen call to confirm intent before writing) — v1.x
- Routing hint in capability refusal (DIFF-03) — v1.x

</deferred>

---

*Phase: 02-promptbuilder*
*Context gathered: 2026-03-28*
