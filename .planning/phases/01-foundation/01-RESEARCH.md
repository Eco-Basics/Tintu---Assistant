# Phase 1: Foundation - Research

**Researched:** 2026-03-28
**Domain:** Python keyword matching, SQLite schema migration, async intent routing
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Capability Refusal — Placement**
- `classify()` runs first on every message
- If intent is `general_answer`, run the capability keyword check before calling `generate()`
- If the check fires, `route()` returns the refusal message immediately — no Ollama call is made
- Task/reminder intents (`set_reminder`, `create_task`, etc.) bypass the refusal check entirely
- Rationale: "remind me to code tonight" correctly classifies as `set_reminder` and passes through; "write me a Python function" classifies as `general_answer` and is refused

**Capability Refusal — Categories**

Refused (on `general_answer` intent):
- Code / programming — both producing AND explaining (e.g., "write a function", "explain recursion", "debug this script")
- Research / external information — anything requiring live or external data (e.g., "what happened in the news today", "find statistics on X")
- Complex analysis on generic topics — multi-step reasoning on topics not in the user's own data
- Generic math / calculation — computation requests not grounded in the user's own stored data (e.g., "solve this equation", "calculate compound interest")

Allowed through (not refused):
- Simple analysis of the user's own stored data (e.g., "what's my average task success rate?") — these classify as `retrieval_query` and never reach the refusal check
- All other intents (`create_task`, `set_reminder`, `list_tasks`, `update_preference`, etc.)

**Capability Refusal — Tone and Forward Direction**
- Refusal message in v1: direct and honest, no apology, no forward routing hint
- Forward routing hint (DIFF-03) is deferred to v1.x
- Message format: one-sentence statement of the limitation. Example: "I can't write or debug code — that's outside what I can do reliably."

**DB Schema — New Tables**

Three new tables are added in this phase:

`personality_traits` — Personality signals detected from natural conversation
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `key` TEXT — signal category (e.g., "communication_style", "response_tone")
- `value` TEXT — captured value (e.g., "direct", "coach")
- `signal_type` TEXT — "tone" | "style" | "persona" | "behavior"
- `confidence` REAL DEFAULT 1.0 — 0.0–1.0, used by DIFF-02 confidence gating (v1.x); schema added now to avoid ALTER TABLE migration later
- `source` TEXT — raw message that triggered the signal
- `created_at` TEXT DEFAULT (datetime('now'))
- `updated_at` TEXT DEFAULT (datetime('now'))

`personas` — On-demand persona definitions
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `name` TEXT — e.g., "brutally honest advisor"
- `description` TEXT — system-prompt fragment for this persona
- `is_active` INTEGER DEFAULT 0 — 1 = currently session-active; only one active at a time
- `created_at` TEXT DEFAULT (datetime('now'))

`behavior_preferences` — The existing `preferences` table already serves this role (key/value/source schema). The planner must decide whether to reuse it as-is, create a distinct `behavior_preferences` table, or treat both as separate concerns.

**DB Schema — Already Exists**
- `conversation_summaries` table already exists in the schema. New columns (`key_facts`, `named_entities`) needed for Phase 3 are deferred to Phase 3.
- No migration versioning needed for Phase 1 — only new tables are being added, which fits the existing `CREATE TABLE IF NOT EXISTS` pattern in `run_migrations()`.

### Claude's Discretion
- Exact keyword/phrase list for each refusal category (code, research, math)
- Whether to use a dict of keyword sets or a flat list with category tags
- Refusal message wording (within the one-sentence, direct-tone constraint)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FOUND-01 | System refuses code, math, and research requests before generation via pre-generation keyword check — no hallucinated answers | Keyword check pattern already exists in `classifier.py` (`KEYWORD_MAP` + `keyword_classify()`). Same `re.search` pattern applies. Check must be placed in `route()` after `classify()` returns `"answer"`, before `build_answer()` is called. |
| FOUND-02 | Database schema is extended with additive migrations for personality_traits, behavior_preferences, personas, conversation_summaries tables — no data loss to existing rows | `run_migrations()` runs `db.executescript(SCHEMA)` which executes all `CREATE TABLE IF NOT EXISTS` statements — idempotent by design. `conversation_summaries` already exists. Two new tables needed: `personality_traits` and `personas`. Planner must decide on `behavior_preferences` vs reusing `preferences`. |
</phase_requirements>

---

## Summary

Phase 1 is a two-part delivery: a capability refusal guard and a schema expansion. Neither requires new libraries or architectural changes — both fit cleanly into the existing codebase patterns.

The capability refusal guard inserts a synchronous keyword check into `route()` in `app/bot/router.py`. The check only fires when `classify()` returns `"answer"` (which maps to `general_answer` intent). This placement guarantees zero Ollama calls for refused messages. The codebase already has `keyword_classify()` in `app/llm/classifier.py` using `re.search` over a `KEYWORD_MAP` dict — the refusal check follows the same pattern but lives in `route()`, not the classifier.

The schema migration adds two new tables (`personality_traits`, `personas`) to the `SCHEMA` string in `app/storage/models.py`. The `run_migrations()` function calls `db.executescript(SCHEMA)` at startup, which is safe for additive changes because all statements use `CREATE TABLE IF NOT EXISTS`. The `conversation_summaries` table already exists — no action needed there for Phase 1. The `behavior_preferences` vs `preferences` question is a planner decision flagged in CONTEXT.md.

**Primary recommendation:** Insert the refusal check as a single `if intent == "answer"` block in `route()` using a `CAPABILITY_REFUSAL` dict of keyword sets (same pattern as `KEYWORD_MAP`), and add two `CREATE TABLE IF NOT EXISTS` blocks to `SCHEMA`. Both changes are self-contained and verifiable by inspection.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `re` | stdlib | Keyword matching via `re.search` | Already used in `classifier.py` `KEYWORD_MAP`; no new dependency |
| `aiosqlite` | 0.20.0 | Async SQLite operations | Already in `requirements.txt`; `run_migrations()` uses it |

### Supporting

No new libraries needed for Phase 1. Both deliverables (refusal check + schema migration) use existing stdlib and project dependencies.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `re.search` keyword dict | spaCy/NLP classifier | Massively over-engineered for a keyword gate; adds a ~150MB dependency for zero user-facing benefit at this phase |
| `CREATE TABLE IF NOT EXISTS` pattern | Alembic or Flyway versioned migrations | Unnecessary complexity — versioned migrations solve ALTER TABLE/index changes; this phase adds only new tables, which `IF NOT EXISTS` handles perfectly |

**Installation:** No new packages required.

---

## Architecture Patterns

### Existing Project Structure (relevant to Phase 1)

```
app/
├── bot/
│   └── router.py          # route() — MODIFY: add refusal check block
├── llm/
│   └── classifier.py      # classify() + keyword_classify() — READ ONLY
├── storage/
│   ├── models.py           # SCHEMA string — MODIFY: add two CREATE TABLE blocks
│   ├── migrations.py       # run_migrations() — NO CHANGE NEEDED
│   └── db.py               # execute(), fetchall() — NO CHANGE NEEDED
```

### Pattern 1: Capability Refusal Check in `route()`

**What:** A pre-`generate()` keyword guard that returns a canned refusal string when `intent == "answer"` and the message matches a capability keyword set.

**When to use:** Every call to `route()` where `classify()` returns `"answer"`.

**Placement in `route()`:**

```python
# app/bot/router.py

# After: intent = await classify(message)
# Before: the draft_reply block and the final build_answer() call

if intent == "answer":
    refusal = _capability_refusal_check(message)
    if refusal:
        logger.info(f"Capability refusal fired | message: {message[:60]!r}")
        return refusal

# ... existing draft_reply block ...
# ... existing fallthrough to build_answer() ...
```

**Refusal check helper (same file or separate module):**

```python
import re

CAPABILITY_REFUSALS = {
    "code": [
        r"\bwrite (a |an |some )?(function|script|program|class|code|snippet)\b",
        r"\bdebug (this|my|the)\b",
        r"\bexplain (this |the )?(code|function|algorithm|recursion|loop)\b",
        r"\bhow (does|do) .{0,40} work (in (python|javascript|code))?\b",
        r"\bfix (this|my|the) (code|bug|error|script)\b",
        r"\brefactor\b",
        r"\bimplementati?on\b",
        r"\b(python|javascript|typescript|sql|bash|html|css|rust|go|java|c\+\+)\b",
    ],
    "math": [
        r"\b(solve|calculate|compute|evaluate|find the value)\b",
        r"\b(equation|integral|derivative|matrix|factorial)\b",
        r"\bwhat is \d+\s*[\+\-\*\/\^]\s*\d+\b",
        r"\bcompound interest\b",
        r"\bpercentage of\b",
    ],
    "research": [
        r"\bwhat (is|are|was|were) the (latest|current|recent|new)\b",
        r"\bwhat('s| is) happening (in|with|to)\b",
        r"\bcurrent events?\b",
        r"\bnews (about|on|today)\b",
        r"\bas of today\b",
        r"\bcheck the (price|weather|rate|status) of\b",
        r"\bfind statistics?\b",
        r"\bwhat is the (population|gdp|rate) of\b",
    ],
}

REFUSAL_MESSAGE = "I can't answer that — code, math, and external research are outside what I can do reliably."

def _capability_refusal_check(message: str) -> str | None:
    text_lower = message.lower()
    for _category, patterns in CAPABILITY_REFUSALS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return REFUSAL_MESSAGE
    return None
```

### Pattern 2: Additive Schema Migration

**What:** Append new `CREATE TABLE IF NOT EXISTS` blocks to the `SCHEMA` string in `models.py`. `run_migrations()` runs `executescript(SCHEMA)` at startup — safe because all statements are idempotent.

**When to use:** Any time a new table is added. Do NOT use for ALTER TABLE or adding indexes — those need a different approach (not needed in Phase 1).

**Example addition to `SCHEMA`:**

```python
# app/storage/models.py — append to existing SCHEMA string

"""
CREATE TABLE IF NOT EXISTS personality_traits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    confidence  REAL DEFAULT 1.0,
    source      TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS personas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    is_active   INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""
```

### Anti-Patterns to Avoid

- **Post-generation refusal check:** Never inspect Qwen's output for code content and prepend a disclaimer. By then the model has spent inference cycles and may have produced harmful content. The guard MUST be pre-generation.
- **Refusal in `build_answer()` instead of `route()`:** The check must live in `route()` to guarantee no Ollama call occurs. `build_answer()` calls `generate()` directly — adding a check there still results in the LLM being invoked.
- **Modifying `classify()` to return a new "refused" intent:** The classifier is a pure intent detector. Mixing capability-refusal logic into classification couples two orthogonal concerns and makes unit testing harder.
- **ALTER TABLE for new columns:** `executescript()` will raise if the column already exists and the statement isn't wrapped in IF NOT EXISTS. Phase 1 adds only new tables — no ALTER statements needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Keyword matching | Custom tokenizer or substring scan | `re.search` with `re.IGNORECASE` equivalent (use `.lower()` first per existing pattern) | Already proven in `KEYWORD_MAP`; handles word boundaries correctly via `\b`; zero new code |
| Migration versioning | Custom version table + migration runner | `CREATE TABLE IF NOT EXISTS` in `executescript()` | Alembic etc. solve ALTER TABLE ordering problems; this phase has none of those |
| Refusal category detection | LLM call to classify whether message is code/math/research | Pre-generation keyword dict | The entire point is to avoid LLM calls; an LLM-based refusal classifier defeats itself |

**Key insight:** Both deliverables in Phase 1 are pure data changes — one is a conditional string return in a routing function, one is DDL appended to a string constant. No new abstractions, no new dependencies, no async complexity.

---

## Common Pitfalls

### Pitfall 1: `draft_reply` Intent Contains Code Keywords
**What goes wrong:** A message like "write a message to my manager about the deployment" classifies as `draft_reply` (correct), but if the refusal check runs on `draft_reply` intents too, it fires incorrectly on "write" + "deployment".
**Why it happens:** The refusal check is placed too early — before the intent check — or is accidentally applied to all intents instead of only `"answer"`.
**How to avoid:** The check MUST be gated behind `if intent == "answer":`. All other intents have already been dispatched before the fallthrough to `build_answer()`. See the placement example in Architecture Patterns above.
**Warning signs:** Users can't draft messages containing technical words; "draft a deployment announcement" returns a refusal.

### Pitfall 2: `executescript()` Silently Swallows SQL Errors
**What goes wrong:** A syntax error in a new `CREATE TABLE` block is silently swallowed by `executescript()` in some aiosqlite versions, or the startup log shows "Database ready" but the table was never created.
**Why it happens:** `executescript()` executes all statements in one batch. An error in statement N does not prevent statements 1 through N-1 from committing. Post-startup schema inspection is the only way to know.
**How to avoid:** After adding new DDL to `SCHEMA`, verify the table exists immediately after startup: `SELECT name FROM sqlite_master WHERE type='table' AND name='personality_traits'`. This is also the acceptance criterion for FOUND-02.
**Warning signs:** Phase 2 code fails with "no such table: personality_traits" despite successful startup log.

### Pitfall 3: Keyword Regex Matches Too Broadly on Short Messages
**What goes wrong:** "How does this work?" fires the code refusal pattern `r"\bhow (does|do)"` and refuses a legitimate conversational question.
**Why it happens:** Short, context-free patterns catch more than intended when applied to general conversation.
**How to avoid:** Require domain context in the pattern: `r"\bhow (does|do) .{0,40} (code|algorithm|function|script|program) work\b"`. Review each pattern in isolation with test strings before committing. Log every triggered refusal (category + first 60 chars of message) — this builds a corpus for tuning.
**Warning signs:** Users report refused messages that don't sound like code/math/research requests; refusal log shows high volume of short messages.

### Pitfall 4: `behavior_preferences` Decision Left Unresolved
**What goes wrong:** FOUND-02's acceptance criterion lists four tables including `behavior_preferences`. If the planner defers this decision to implementation, the implementer may create a new table that duplicates the existing `preferences` table, causing Phase 2's PromptBuilder to read from the wrong table.
**Why it happens:** The CONTEXT.md explicitly flags this as a planner decision. If not resolved in the PLAN, implementation defaults to "create a new table" because that's the path of least resistance.
**How to avoid:** The PLAN.md MUST resolve this: either (a) `behavior_preferences` is an alias for the existing `preferences` table (no new table, requirement satisfied by existing schema), or (b) a distinct `behavior_preferences` table is created with explicit migration strategy. Recommendation: reuse `preferences` as-is and document the mapping. The `preferences` table has exactly the right schema (key/value/source/timestamps) and is already written by `update_preference`.
**Warning signs:** Phase 2 has two tables with overlapping semantics; PromptBuilder assembles personality from one and ignores the other.

---

## Code Examples

Verified patterns from codebase direct inspection:

### Existing `keyword_classify()` Pattern (from `app/llm/classifier.py`)

```python
# Source: app/llm/classifier.py lines 93-99
def keyword_classify(text: str) -> str | None:
    text_lower = text.lower()
    for intent, patterns in KEYWORD_MAP.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return intent
    return None
```

The capability refusal check follows this exact pattern — dict of category → list of regex patterns, iterate, `re.search` on lowercased text.

### Existing `route()` Intent Dispatch Pattern (from `app/bot/router.py`)

```python
# Source: app/bot/router.py lines 35-199
async def route(message: str) -> str:
    intent = await classify(message)
    logger.info(f"Intent: {intent} | message: {message[:60]!r}")

    if intent == "capture_note":
        ...
    if intent == "create_task":
        ...
    # ... other intents ...

    # ── Default: answer ───────────────────────────────────────────────
    return await build_answer(message)
```

The refusal check is a new conditional block inserted between the last named-intent block and the final `return await build_answer(message)` line.

### Existing `run_migrations()` Pattern (from `app/storage/migrations.py`)

```python
# Source: app/storage/migrations.py lines 8-13
async def run_migrations():
    logger.info("Running database migrations...")
    async with await get_db() as db:
        await db.executescript(SCHEMA)
        await db.commit()
    logger.info("Database ready.")
```

Adding tables to `SCHEMA` is the complete and correct migration path for Phase 1.

### `SCHEMA` Append Position

The two new tables must be appended to the existing `SCHEMA` string in `app/storage/models.py` after the `message_log` table block (line 103). No changes to `run_migrations()` or `db.py` are needed.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Post-generation content filter | Pre-generation keyword check | Established pattern (PITFALLS.md Pitfall 6) | Guarantees no hallucinated output reaches user; no LLM cycles wasted on refused queries |
| `schema.sql` file with manual migration | `CREATE TABLE IF NOT EXISTS` in Python string, `executescript()` at startup | Already established in this codebase | Idempotent startup migration with no external tooling dependency |

**Deprecated/outdated:**
- Adding capability filtering as post-processing on `generate()` output: this is the pattern this phase explicitly replaces. Never do this.

---

## Open Questions

1. **`behavior_preferences` vs `preferences` table**
   - What we know: `preferences` table already exists with key/value/source schema, written by `update_preference` intent. FOUND-02 lists `behavior_preferences` as a required table.
   - What's unclear: Whether the acceptance criterion requires a distinct `behavior_preferences` table or whether the existing `preferences` table satisfies the requirement by fulfilling the same semantic role.
   - Recommendation: Planner resolves this in PLAN.md. My recommendation is to document `preferences` as fulfilling the `behavior_preferences` role — adding a redundant table creates Phase 2 ambiguity about which table the PromptBuilder reads.

2. **Refusal log destination**
   - What we know: PITFALLS.md recommends logging every triggered refusal with the original message.
   - What's unclear: Whether to log to the `message_log` table (existing) or just the application logger.
   - Recommendation: Python logger at INFO level is sufficient for Phase 1. The `message_log` table could be extended in a later phase if refusal analytics become useful.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (not installed — see Wave 0) |
| Config file | none — see Wave 0 |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FOUND-01 | Code request returns refusal string without calling `generate()` | unit | `pytest tests/test_refusal.py -x` | Wave 0 |
| FOUND-01 | Math request returns refusal string without calling `generate()` | unit | `pytest tests/test_refusal.py::test_math_refusal -x` | Wave 0 |
| FOUND-01 | Research request returns refusal string without calling `generate()` | unit | `pytest tests/test_refusal.py::test_research_refusal -x` | Wave 0 |
| FOUND-01 | `set_reminder` with code word passes through (no refusal) | unit | `pytest tests/test_refusal.py::test_non_answer_bypass -x` | Wave 0 |
| FOUND-01 | `retrieval_query` intent bypasses refusal check entirely | unit | `pytest tests/test_refusal.py::test_retrieval_bypass -x` | Wave 0 |
| FOUND-02 | `personality_traits` table exists after migration | integration | `pytest tests/test_migrations.py::test_personality_traits_table -x` | Wave 0 |
| FOUND-02 | `personas` table exists after migration | integration | `pytest tests/test_migrations.py::test_personas_table -x` | Wave 0 |
| FOUND-02 | Migration is idempotent (running twice does not error) | integration | `pytest tests/test_migrations.py::test_migration_idempotent -x` | Wave 0 |
| FOUND-02 | Existing `preferences` rows survive migration | integration | `pytest tests/test_migrations.py::test_existing_rows_preserved -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/__init__.py` — package marker
- [ ] `tests/conftest.py` — shared async fixtures (in-memory aiosqlite DB, mock `generate()`)
- [ ] `tests/test_refusal.py` — covers FOUND-01 (all 5 test cases above)
- [ ] `tests/test_migrations.py` — covers FOUND-02 (all 4 test cases above)
- [ ] Framework install: `pip install pytest pytest-asyncio` — pytest not in requirements.txt

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection: `app/bot/router.py` — `route()` function, intent dispatch pattern
- Direct codebase inspection: `app/llm/classifier.py` — `keyword_classify()`, `KEYWORD_MAP` pattern
- Direct codebase inspection: `app/storage/models.py` — `SCHEMA` string, existing table definitions
- Direct codebase inspection: `app/storage/migrations.py` — `run_migrations()`, `executescript()` pattern
- Direct codebase inspection: `app/llm/response_builder.py` — `build_answer()` call chain
- `.planning/phases/01-foundation/01-CONTEXT.md` — all locked decisions
- `.planning/REQUIREMENTS.md` — FOUND-01 and FOUND-02 acceptance criteria
- `.planning/research/PITFALLS.md` — Pitfall 6 (capability refusal must be pre-generation)

### Secondary (MEDIUM confidence)

- `.planning/research/FEATURES.md` — "Table Stakes: Honest capability limits" and "Anti-Features: No fallback model" sections

### Tertiary (LOW confidence)

None — all findings derive from direct codebase inspection and project documents.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; existing `re` and `aiosqlite` patterns verified from codebase
- Architecture: HIGH — refusal placement and schema migration pattern verified from live code
- Pitfalls: HIGH — derived from direct codebase analysis and PITFALLS.md Pitfall 6 (domain-expert-level research)

**Research date:** 2026-03-28
**Valid until:** 2026-06-28 (stable domain — Python stdlib `re`, SQLite DDL, established codebase patterns; no external library versions at risk of breaking change)
