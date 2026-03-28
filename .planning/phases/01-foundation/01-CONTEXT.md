# Phase 1: Foundation - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a capability refusal guard to the general-answer path and create the database tables that Phase 2 (PromptBuilder) and Phase 3 (Context Budget Manager) depend on. No personality behavior is active after this phase — the tables exist and refusal fires, but nothing reads from them yet.

</domain>

<decisions>
## Implementation Decisions

### Capability Refusal — Placement

- `classify()` runs first on every message
- If intent is `general_answer`, run the capability keyword check before calling `generate()`
- If the check fires, `route()` returns the refusal message immediately — no Ollama call is made
- Task/reminder intents (`set_reminder`, `create_task`, etc.) bypass the refusal check entirely
- **Rationale:** "remind me to code tonight" correctly classifies as `set_reminder` and passes through; "write me a Python function" classifies as `general_answer` and is refused

### Capability Refusal — Categories

Refused (on `general_answer` intent):
- **Code / programming** — both producing AND explaining (e.g., "write a function", "explain recursion", "debug this script")
- **Research / external information** — anything requiring live or external data (e.g., "what happened in the news today", "find statistics on X")
- **Complex analysis on generic topics** — multi-step reasoning on topics not in the user's own data
- **Generic math / calculation** — computation requests not grounded in the user's own stored data (e.g., "solve this equation", "calculate compound interest")

**Allowed through (not refused):**
- Simple analysis of the user's own stored data (e.g., "what's my average task success rate?") — these classify as `retrieval_query` and never reach the refusal check
- All other intents (`create_task`, `set_reminder`, `list_tasks`, `update_preference`, etc.)

### Capability Refusal — Tone and Forward Direction

- Refusal message in v1: direct and honest, no apology, no forward routing hint
- Forward routing hint (DIFF-03: "I can't debug this, but I can note it as a task") is deferred to v1.x
- Message format: one-sentence statement of the limitation. Example: "I can't write or debug code — that's outside what I can do reliably."

### DB Schema — New Tables

Three new tables are added in this phase:

**`personality_traits`** — Personality signals detected from natural conversation
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `key` TEXT — signal category (e.g., "communication_style", "response_tone")
- `value` TEXT — captured value (e.g., "direct", "coach")
- `signal_type` TEXT — "tone" | "style" | "persona" | "behavior"
- `confidence` REAL DEFAULT 1.0 — 0.0–1.0, used by DIFF-02 confidence gating (v1.x); schema added now to avoid ALTER TABLE migration later
- `source` TEXT — raw message that triggered the signal
- `created_at` TEXT DEFAULT (datetime('now'))
- `updated_at` TEXT DEFAULT (datetime('now'))

**`personas`** — On-demand persona definitions
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `name` TEXT — e.g., "brutally honest advisor"
- `description` TEXT — system-prompt fragment for this persona
- `is_active` INTEGER DEFAULT 0 — 1 = currently session-active; only one active at a time
- `created_at` TEXT DEFAULT (datetime('now'))

**`behavior_preferences`** — Note: the existing `preferences` table already serves this role (key/value/source schema). The planner should decide whether to:
  - Reuse the existing `preferences` table as-is (no new table needed)
  - Create a distinct `behavior_preferences` table and migrate existing data
  - Treat both as separate concerns going forward

This is flagged for the planner to resolve. No new `behavior_preferences` table is prescribed here.

### DB Schema — Already Exists

- `conversation_summaries` table already exists in the schema. New columns (`key_facts`, `named_entities`) needed for Phase 3 are deferred to Phase 3.
- No migration versioning needed for Phase 1 — only new tables are being added, which fits the existing `CREATE TABLE IF NOT EXISTS` pattern in `run_migrations()`.

### Claude's Discretion

- Exact keyword/phrase list for each refusal category (code, research, math)
- Whether to use a dict of keyword sets or a flat list with category tags
- Refusal message wording (within the one-sentence, direct-tone constraint)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs or ADRs — this project has no separate spec documents. Requirements are fully captured in the decisions above and the files below.

### Requirements
- `.planning/REQUIREMENTS.md` — FOUND-01 (capability refusal) and FOUND-02 (schema migration) acceptance criteria

### Research
- `.planning/research/PITFALLS.md` — Pitfall 6: capability refusal must be pre-generation keyword check, not post-processing. Review before designing the keyword matching approach.
- `.planning/research/FEATURES.md` — "Table Stakes" section: "Honest capability limits" and "Anti-Features" section: "No fallback model"

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/bot/router.py` → `route()`: Single entry point for all messages. Refusal check and classify() call both live here. No other files need modification for the refusal feature.
- `app/storage/models.py` → `SCHEMA`: New tables are added as `CREATE TABLE IF NOT EXISTS` blocks. Migration is automatic on startup via `run_migrations()` in `app/storage/migrations.py`.
- `app/storage/db.py` → `execute()`, `fetchall()`: Standard async DB helpers. New table reads in Phase 2 use these directly.

### Established Patterns
- **Migration pattern**: Add `CREATE TABLE IF NOT EXISTS` to `SCHEMA` string in `models.py` → `run_migrations()` picks it up on next startup. Idempotent, no versioning needed for new-table-only changes.
- **Intent dispatch**: `route()` classifies with `classify()`, then dispatches via `if intent == "..."` blocks. Refusal check inserts as a conditional block after `intent = await classify(message)`.
- **Existing `preferences` table**: Already has key/value/source schema and is written by the `update_preference` intent handler. Semantically equivalent to `behavior_preferences`. Planner should resolve whether to extend this or create a new table.

### Integration Points
- `app/llm/classifier.py` → `classify()`: Returns the intent string. Refusal check reads the return value from this call.
- `app/storage/models.py` → `SCHEMA`: Where new table DDL is added.
- `app/storage/migrations.py` → `run_migrations()`: Called at bot startup; no changes needed here.

</code_context>

<specifics>
## Specific Ideas

- User confirmed: simple data queries ("what's my average success rate on task X?") use the user's own stored data and should pass through — they're retrieval queries, not generic math.
- User confirmed: both explaining AND producing code should be refused — Qwen3:4b's explanations of code concepts are also unreliable.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-03-28*
