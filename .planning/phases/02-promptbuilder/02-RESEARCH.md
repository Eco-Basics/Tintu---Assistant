# Phase 2: PromptBuilder - Research

**Researched:** 2026-03-28
**Domain:** Dynamic system prompt assembly from SQLite, async Python, preference confirmation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Prompt section order:** base identity → behavior preferences → personality traits → active persona
- **Conditional inclusion:** each section included only if it has content, except `personality_traits` which always includes a placeholder line ("Personality traits: none yet") when the table is empty
- **Base identity:** existing `SYSTEM_PROMPT` string, content unchanged, becomes the first section
- **Behavior preferences:** all rows from the `preferences` table formatted as natural language instructions
- **Personality traits:** all rows from `personality_traits` table; if empty, show "Personality traits: none yet"
- **Active persona:** if any row in `personas` has `is_active=1`, appended as "For this session, adopt the following persona: [description]." — supplements base identity, does not replace it
- **Which calls get the dynamic prompt:** `build_answer()`, `draft_reply` block in router.py, `build_retrieval_answer()`, `build_compare_answer()` — all user-facing answer calls
- **Which calls stay on static prompts:** all extraction calls (TASK_EXTRACT_PROMPT, REMINDER_EXTRACT_PROMPT, PREFERENCE_EXTRACT_PROMPT, DECISION_EXTRACT_PROMPT, COMPLETE_TASK_EXTRACT_PROMPT) — must not be influenced by personality context
- **DEBUG logging:** `logger.debug(f"system_prompt=\n{assembled_prompt}")` on every assembled prompt — full string, no truncation — logged in the assembler module before the Ollama call
- **Preference confirmation format:** `"Saved: [natural language restatement]"` e.g. "Saved: I'll be more direct with you" — replaces the current `"Preference saved: *{key}* = {value}"`
- **`preferences` table compatibility:** confirmed — no schema changes needed in Phase 2
- **Trait detection:** out of scope — Phase 2 only reads from `personality_traits`, nothing writes to it

### Claude's Discretion

- Exact module location for PromptBuilder (new file `app/llm/prompt_builder.py` is the natural choice, but planner decides)
- Exact string format for each preferences row in the assembled prompt (natural language transform vs key=value)
- Whether to use a Qwen call or template string for preference confirmation echo — either is acceptable
- Caching strategy for assembled prompt within a single request cycle (not across requests)

### Deferred Ideas (OUT OF SCOPE)

- Automatic personality trait detection from natural conversation messages — future phase
- Confidence-gated trait persistence (DIFF-02) — v1.x
- Routing hint in capability refusal (DIFF-03) — v1.x
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERS-01 | System assembles the Ollama system prompt dynamically from `personality_traits` and `behavior_preferences` tables on each request — stored preferences are reflected in every answer | `build_system_prompt()` async function reads all three tables via `fetchall()` and concatenates sections; injected via the existing `generate(system=...)` parameter |
| PERS-04 | When a preference is saved, assistant echoes confirmation ("Saved: I'll be more direct with you") — user can verify capture without querying the database | Change the `update_preference` return string in `router.py` from `"Preference saved: *{key}* = {value}"` to a natural-language echo; generated via lightweight Qwen call or simple template |
</phase_requirements>

---

## Summary

Phase 2 is a surgical replacement of the static `SYSTEM_PROMPT` string with a dynamically assembled string read from three database tables on every user-facing Ollama call. The code surface is small: one new module (`app/llm/prompt_builder.py`), changes to four call sites in `response_builder.py` and `router.py`, and a change to the preference confirmation string in `router.py`.

All infrastructure is already in place. The `generate()` function in `ollama_client.py` already accepts a `system` keyword argument. The `fetchall()` helper in `db.py` is already used throughout the codebase. The `preferences` table is already written and read in `router.py`. The `personality_traits` and `personas` tables are added in Phase 1's migration and will exist (empty) by the time Phase 2 executes.

The one design decision left to the planner is the preference confirmation echo: a simple Python template that converts `key`/`value` from the extract result into a natural-language sentence is adequate, avoids an extra Qwen round-trip, and keeps the call synchronous within the existing `update_preference` block.

**Primary recommendation:** Create `app/llm/prompt_builder.py` with a single async function `build_system_prompt() -> str`. Replace `SYSTEM_PROMPT` at the four call sites. Change the preference confirmation return string. Add one DEBUG log line inside `build_system_prompt`.

---

## Standard Stack

### Core (all already in project — no new installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `aiosqlite` | project-pinned | Async SQLite reads for prompt assembly | Already used via `fetchall()` in `db.py` |
| `logging` (stdlib) | Python stdlib | DEBUG log of assembled prompt | Already used with `logging.getLogger(__name__)` pattern |
| `httpx` | project-pinned | Ollama HTTP calls (unchanged) | Already used in `ollama_client.py` |

**No new dependencies.** Phase 2 uses only what is already installed.

---

## Architecture Patterns

### Recommended Project Structure

No new directories. One new file:

```
app/llm/
├── classifier.py          # unchanged
├── ollama_client.py       # unchanged
├── prompt_builder.py      # NEW — build_system_prompt()
├── prompts.py             # unchanged (SYSTEM_PROMPT stays as base identity constant)
└── response_builder.py    # 3 call sites updated
app/bot/
└── router.py              # draft_reply call site + update_preference confirmation updated
```

### Pattern 1: Single Async Assembly Function

**What:** `build_system_prompt()` is a single async function that runs three `fetchall()` queries and concatenates sections. It is the only public API of the module.

**When to use:** Called directly at every user-facing Ollama call site (four total). Not cached across requests — fresh DB read on each call.

**Why no caching:** Each call is a SQLite in-process read of small tables (likely < 20 rows total). The overhead is negligible compared to the Ollama HTTP round-trip (90 s timeout). Caching introduces stale-read complexity with no measurable performance benefit for this workload.

**Call pattern (all four sites follow the same substitution):**

```python
# Before (all four sites):
await generate(prompt, system=SYSTEM_PROMPT)

# After:
system = await build_system_prompt()
await generate(prompt, system=system)
```

### Pattern 2: Section Construction with Conditional Inclusion

**What:** Each section is built as a string fragment, then joined. Empty fragments are omitted (except personality_traits which always includes the placeholder).

```python
# Pseudocode — planner resolves exact string formatting
sections = []

# Section 1: base identity (always present)
sections.append(SYSTEM_PROMPT)

# Section 2: behavior preferences (only if rows exist)
prefs = await fetchall("SELECT key, value FROM preferences")
if prefs:
    pref_lines = "\n".join(f"- {row['value']}." for row in prefs)
    sections.append(f"Behavior preferences:\n{pref_lines}")

# Section 3: personality traits (always present — placeholder if empty)
traits = await fetchall("SELECT key, value FROM personality_traits")
if traits:
    trait_lines = "\n".join(f"- {row['key']}: {row['value']}" for row in traits)
    sections.append(f"Personality traits:\n{trait_lines}")
else:
    sections.append("Personality traits: none yet")

# Section 4: active persona (only if is_active=1 row exists)
personas = await fetchall("SELECT description FROM personas WHERE is_active=1 LIMIT 1")
if personas:
    sections.append(f"For this session, adopt the following persona: {personas[0]['description']}.")

assembled = "\n\n".join(sections)
logger.debug(f"system_prompt=\n{assembled}")
return assembled
```

**Note on preferences formatting:** The value column in the `preferences` table already contains the semantic content (e.g., "more direct", "skip confirmation"). The CONTEXT.md decision requires natural language instructions. The planner may choose:
  - Option A (simple): Use `value` directly as a sentence — `f"- {row['value']}."` — works if value is stored as a phrase
  - Option B (template): Use both key and value — `f"- {row['key'].replace('_', ' ')}: {row['value']}."` — more explicit
  - Option C (transform): A Qwen call per preference to generate a sentence — avoids an extra LLM call; CONTEXT.md says Claude's discretion

Option A is the minimum viable path. The planner should decide between A and B based on how the PREFERENCE_EXTRACT_PROMPT currently structures the value field (it stores things like "more direct" not full sentences).

### Pattern 3: Preference Confirmation Echo (PERS-04)

**What:** Replace the literal `f"Preference saved: *{key}* = {value}"` in the `update_preference` block with a natural-language string.

**Template approach (no extra Qwen call):**

```python
# Current (line 144 in router.py):
return f"Preference saved: *{key}* = {value}"

# New — template transform using the `source` field from PREFERENCE_EXTRACT_PROMPT:
echo = f"Saved: I'll {source.lower().rstrip('.')}."
# e.g., source = "be more direct" → "Saved: I'll be more direct."
```

**Qwen call approach (alternative if template is insufficient):**

```python
echo_prompt = f"Restate this preference as a first-person confirmation starting with 'Saved: '.\nPreference: {key} = {value}"
echo = await generate(echo_prompt)
return echo
```

The template approach is lower latency and simpler. It works when `source` is a natural-language description (which PREFERENCE_EXTRACT_PROMPT produces: "Source: natural language description of what was said"). The planner should prefer the template approach unless the source field proves too noisy in testing.

### Pattern 4: compare_against_prior Integration

**What:** `build_compare_answer()` in `response_builder.py` calls `compare_against_prior()` in `comparison.py`. That function calls `generate(prompt)` with no system argument — it uses the default empty string, so no SYSTEM_PROMPT is applied today.

**CONTEXT.md decision:** `build_compare_answer()` should receive the dynamic prompt.

**Resolution:** `build_compare_answer()` must be updated to pass `system=` down into `compare_against_prior()`, or `compare_against_prior()` must accept and pass through a `system` parameter.

**Simplest path:** Update `compare_against_prior` to accept `system: str = ""` and pass it to `generate()`. Then `build_compare_answer()` assembles the prompt and passes it through. This is a two-line change in `comparison.py`.

### Anti-Patterns to Avoid

- **Injecting personality into extraction calls:** `TASK_EXTRACT_PROMPT`, `REMINDER_EXTRACT_PROMPT`, `PREFERENCE_EXTRACT_PROMPT`, `DECISION_EXTRACT_PROMPT`, `COMPLETE_TASK_EXTRACT_PROMPT` must pass `system=""` or omit the system arg (current behavior) — never the dynamic prompt. These are structured-output calls; personality instructions corrupt the parse.
- **Logging the assembled prompt inside `generate()`:** The DEBUG log must be in `build_system_prompt()` before the Ollama call, not inside `ollama_client.py`. This satisfies the requirement that the log appears before the Ollama call and is visible even if the call fails.
- **Truncating the DEBUG log:** `logger.debug(f"system_prompt=\n{assembled_prompt}")` — no `[:500]` or similar truncation. The full string must appear.
- **Caching across requests:** Do not persist the assembled string at module level or in a class instance. The prompt must be fresh on every call to reflect preference changes immediately.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async DB reads | Custom connection management | `fetchall()` from `app/storage/db.py` | Already handles connection lifecycle, WAL mode, row_factory |
| String section joining | Custom separator logic | `"\n\n".join(sections)` | Standard Python; sections list naturally omits empties |
| Preference template transform | Separate NLP layer | Simple f-string on `source` field | PREFERENCE_EXTRACT_PROMPT already captures "Source: natural language description" |

**Key insight:** This phase is assembly, not invention. Every building block exists. The work is wiring.

---

## Common Pitfalls

### Pitfall 1: compare_against_prior bypasses the system parameter

**What goes wrong:** `build_compare_answer()` delegates to `compare_against_prior()`, which calls `generate(prompt)` with no system arg. After updating `build_compare_answer()` to assemble the dynamic prompt, the personality is still not applied because `comparison.py` never receives it.

**Why it happens:** The indirection through `comparison.py` hides the call site. Easy to update `response_builder.py` and miss the downstream call.

**How to avoid:** `comparison.py`'s `compare_against_prior()` function must be updated to accept and pass through a `system: str = ""` parameter. This is a two-line change: add the parameter, pass it to `generate()`.

**Warning signs:** DEBUG log shows the assembled system_prompt, but the compare_context responses still sound like the static base identity with no preferences applied.

### Pitfall 2: Preference extraction call receives dynamic prompt

**What goes wrong:** The `update_preference` handler calls `generate(PREFERENCE_EXTRACT_PROMPT.format(message=message))` with no system arg today. If someone adds a blanket `system=await build_system_prompt()` to all `generate()` calls in router.py, the extraction call also gets the dynamic prompt.

**Why it happens:** Convenience refactor that applies the dynamic system to all `generate()` calls in scope.

**How to avoid:** Extraction calls must explicitly pass `system=""` or continue with no system arg. Only the four user-facing answer calls get the dynamic prompt. The CONTEXT.md decision is explicit on this.

**Warning signs:** Preference extraction starts hallucinating non-key/value output, or the `_parse_kv()` function returns empty/garbled keys.

### Pitfall 3: personality_traits table does not exist at Phase 2 execution time

**What goes wrong:** Phase 2 executes before Phase 1 completes. The `personality_traits` table is not yet in the schema. `fetchall("SELECT key, value FROM personality_traits")` throws `sqlite3.OperationalError: no such table`.

**Why it happens:** Phase sequencing — Phase 2 depends on Phase 1 migration.

**How to avoid:** The planner must document Phase 1 as a hard prerequisite. The `build_system_prompt()` function could defensively use `SELECT ... FROM personality_traits` inside a try/except, but the correct fix is execution order. The try/except approach masks Phase 1 failures silently.

**Warning signs:** Bot startup fails at first `route()` call with an OperationalError on `personality_traits` or `personas`.

### Pitfall 4: DEBUG log level not enabled in production config

**What goes wrong:** `logger.debug(...)` calls are silently dropped because the logger level is INFO or WARNING in the running environment.

**Why it happens:** Standard Python logging defaults to WARNING; project may configure INFO.

**How to avoid:** PERS-01 success criterion 4 requires the DEBUG log to be visible. Verify the logging config (likely in `app/config.py` or startup) supports DEBUG level. This is a verification step, not a code change in `prompt_builder.py`.

**Warning signs:** The assembled prompt never appears in logs even after setting a preference. Check `logging.basicConfig(level=logging.DEBUG)` or equivalent.

### Pitfall 5: Preference value format mismatch with natural language instructions

**What goes wrong:** The `preferences` table `value` column contains raw values like `"direct"` (not `"be more direct"`). The assembled prompt section reads `"Be more direct."` but the value stored is just `"direct"` — requires a key-aware transform.

**Why it happens:** PREFERENCE_EXTRACT_PROMPT instructs the model to extract `Value: <the preference value>` — the value could be a bare noun, adjective, or a phrase depending on what the model extracts.

**How to avoid:** Use the `source` field (which is the natural language description) rather than `value` alone for the human-readable instruction. Or test the PREFERENCE_EXTRACT_PROMPT output for a few real messages and decide on Option A/B/C from the Pattern 2 discussion.

---

## Code Examples

### build_system_prompt() — verified integration with existing generate() signature

```python
# app/llm/prompt_builder.py
import logging
from app.llm.prompts import SYSTEM_PROMPT
from app.storage.db import fetchall

logger = logging.getLogger(__name__)


async def build_system_prompt() -> str:
    sections = [SYSTEM_PROMPT]

    prefs = await fetchall("SELECT key, value FROM preferences ORDER BY updated_at DESC")
    if prefs:
        lines = "\n".join(f"- {row['value']}." for row in prefs)
        sections.append(f"Behavior preferences:\n{lines}")

    traits = await fetchall("SELECT key, value FROM personality_traits")
    if traits:
        lines = "\n".join(f"- {row['key']}: {row['value']}" for row in traits)
        sections.append(f"Personality traits:\n{lines}")
    else:
        sections.append("Personality traits: none yet")

    personas = await fetchall(
        "SELECT description FROM personas WHERE is_active=1 LIMIT 1"
    )
    if personas:
        sections.append(
            f"For this session, adopt the following persona: {personas[0]['description']}."
        )

    assembled = "\n\n".join(sections)
    logger.debug(f"system_prompt=\n{assembled}")
    return assembled
```

### Updated call sites — response_builder.py

```python
# app/llm/response_builder.py
from app.llm.ollama_client import generate
from app.llm.prompt_builder import build_system_prompt
from app.memory.retrieval import retrieve_context


async def build_answer(message: str) -> str:
    system = await build_system_prompt()
    return await generate(message, system=system)


async def build_retrieval_answer(message: str) -> str:
    context = await retrieve_context(message)
    prompt = f"Context from memory:\n{context}\n\nUser question: {message}" if context else message
    system = await build_system_prompt()
    return await generate(prompt, system=system)


async def build_compare_answer(message: str) -> str:
    from app.memory.comparison import compare_against_prior
    system = await build_system_prompt()
    return await compare_against_prior(message, system=system)
```

### comparison.py — accept and pass through system parameter

```python
# app/memory/comparison.py — minimal change
async def compare_against_prior(new_input: str, system: str = "") -> str:
    context = await retrieve_context(new_input)
    if not context:
        return "No prior context found to compare against."
    prompt = COMPARE_PROMPT.format(new_input=new_input, context=context)
    return await generate(prompt, system=system)
```

### draft_reply call site — router.py

```python
# router.py — draft_reply block
if intent == "draft_reply":
    system = await build_system_prompt()
    draft = await generate(
        f"Draft the following. Return only the draft text, no preamble:\n\n{message}",
        system=system,
    )
    return f"*Draft:*\n\n{draft}\n\n_Reply 'send it' or 'post this' to confirm, or ignore to discard._"
```

### update_preference confirmation echo — router.py

```python
# router.py — update_preference block (PERS-04)
if key and value:
    await execute(
        """INSERT INTO preferences (key, value, source) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value,
           source=excluded.source, updated_at=datetime('now')""",
        (key, value, source),
    )
    # Natural language echo — uses source field from PREFERENCE_EXTRACT_PROMPT
    echo = f"Saved: I'll {source.lower().rstrip('.')}."
    return echo
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `SYSTEM_PROMPT` constant injected at call site | `await build_system_prompt()` assembled from DB | Phase 2 | Personality stored in DB is reflected in every answer without restart |
| `"Preference saved: *{key}* = {value}"` | `"Saved: I'll {source}."` | Phase 2 | User can verify what was captured in natural language |
| `compare_against_prior` ignores system prompt | `compare_against_prior(system=...)` | Phase 2 | Compare answers also reflect personality |

---

## Open Questions

1. **Preference value format in the assembled prompt**
   - What we know: `PREFERENCE_EXTRACT_PROMPT` extracts `Value:` and `Source:` separately. Source is "natural language description of what was said."
   - What's unclear: Whether the `value` field is consistently a phrase usable as a natural-language instruction, or a bare word requiring the `key` for context.
   - Recommendation: Test `PREFERENCE_EXTRACT_PROMPT` against 3–4 real preference messages before choosing Option A/B/C. The `source` field is the safest fallback for human-readable output.

2. **Preference echo template vs Qwen call**
   - What we know: Both approaches are acceptable per CONTEXT.md. The `source` field contains natural language. The template `f"Saved: I'll {source.lower()}"` works when source is phrased as an action ("be more direct", "skip confirmation before creating tasks").
   - What's unclear: Whether Qwen's extraction of `Source:` is consistently action-verb phrased.
   - Recommendation: Start with template. Add a Qwen call only if integration testing shows the template produces awkward echoes.

3. **Logging level configuration**
   - What we know: PERS-01 requires DEBUG logs to be visible. The project uses `logging.getLogger(__name__)` but the root log level configuration is not visible in the files read.
   - What's unclear: Whether the running service has DEBUG enabled, or whether the planner needs to add a Wave 0 task to verify/set it.
   - Recommendation: Add a verification step to confirm `logging.basicConfig(level=logging.DEBUG)` or equivalent is set. Check `app/config.py` or the bot entrypoint.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (assumed — check `requirements.txt`) |
| Config file | none detected — see Wave 0 |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERS-01 | `build_system_prompt()` returns base identity when all tables are empty | unit | `pytest tests/test_prompt_builder.py::test_empty_tables -x` | ❌ Wave 0 |
| PERS-01 | `build_system_prompt()` includes preferences rows as natural language | unit | `pytest tests/test_prompt_builder.py::test_with_preferences -x` | ❌ Wave 0 |
| PERS-01 | `build_system_prompt()` includes placeholder when `personality_traits` empty | unit | `pytest tests/test_prompt_builder.py::test_empty_traits_placeholder -x` | ❌ Wave 0 |
| PERS-01 | `build_system_prompt()` includes active persona when `is_active=1` | unit | `pytest tests/test_prompt_builder.py::test_active_persona -x` | ❌ Wave 0 |
| PERS-01 | `build_system_prompt()` does NOT include inactive persona | unit | `pytest tests/test_prompt_builder.py::test_inactive_persona_excluded -x` | ❌ Wave 0 |
| PERS-01 | DEBUG log contains full assembled prompt string | unit | `pytest tests/test_prompt_builder.py::test_debug_log -x` | ❌ Wave 0 |
| PERS-01 | `build_answer()` passes dynamic prompt to `generate()` | unit (mock) | `pytest tests/test_response_builder.py::test_dynamic_prompt_injected -x` | ❌ Wave 0 |
| PERS-04 | Preference confirmation echo is natural language | unit | `pytest tests/test_router.py::test_preference_echo_format -x` | ❌ Wave 0 |
| PERS-04 | Preference confirmation starts with "Saved: " | unit | `pytest tests/test_router.py::test_preference_echo_prefix -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_prompt_builder.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_prompt_builder.py` — covers PERS-01 unit tests (requires async test support; use `pytest-asyncio`)
- [ ] `tests/test_response_builder.py` — covers PERS-01 integration with `build_answer()`, mock `generate()`
- [ ] `tests/test_router.py` — covers PERS-04 preference echo tests
- [ ] `tests/conftest.py` — shared async fixtures for in-memory SQLite with Phase 1 schema applied
- [ ] Framework: `pip install pytest pytest-asyncio` if not already in `requirements.txt`

---

## Sources

### Primary (HIGH confidence)

- Direct code reading: `app/llm/response_builder.py` — `build_answer()`, `build_retrieval_answer()`, `build_compare_answer()` call sites
- Direct code reading: `app/llm/ollama_client.py` — `generate(prompt, system="", model=..., timeout=...)` signature confirmed
- Direct code reading: `app/llm/prompts.py` — `SYSTEM_PROMPT` string and all extraction prompts
- Direct code reading: `app/bot/router.py` — `draft_reply` block (line 192–196), `update_preference` block (lines 131–145), exact current return string
- Direct code reading: `app/storage/db.py` — `fetchall()`, `execute()` signatures
- Direct code reading: `app/storage/migrations.py` — migration pattern (`executescript(SCHEMA)` on startup)
- Direct code reading: `app/memory/comparison.py` — `compare_against_prior()` missing `system` parameter
- `.planning/phases/02-promptbuilder/02-CONTEXT.md` — all locked decisions
- `.planning/phases/01-foundation/01-CONTEXT.md` — `personality_traits` and `personas` column specs

### Secondary (MEDIUM confidence)

- `.planning/REQUIREMENTS.md` — PERS-01 and PERS-04 acceptance criteria

### Notes on models.py observation

`app/storage/models.py` currently does NOT contain `personality_traits` or `personas` table DDL — those are Phase 1 additions. This confirms Phase 2 has a hard dependency on Phase 1 execution. The research notes this explicitly in Pitfall 3.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are project-incumbent, no new dependencies
- Architecture: HIGH — all integration points verified by direct code reading; no unknowns
- Pitfalls: HIGH — derived from concrete code analysis (e.g., `compare_against_prior` missing system param is a verified gap, not a guess)
- Test infrastructure: MEDIUM — `requirements.txt` not read; pytest presence assumed; Wave 0 gaps flagged

**Research date:** 2026-03-28
**Valid until:** Stable — no fast-moving dependencies; valid until Phase 1 schema changes or Ollama API changes
