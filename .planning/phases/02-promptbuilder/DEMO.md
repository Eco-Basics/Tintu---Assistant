# Phase 2 Demo: PromptBuilder

## What Was Built

Every Ollama call now uses a dynamically assembled system prompt built from the user's stored data:

1. **build_system_prompt()** — New function in `app/llm/prompt_builder.py` that reads `preferences`, `personality_traits`, and `personas` tables and assembles them into a structured system prompt at request time.

2. **Call-site wiring** — All four user-facing answer functions (`build_answer`, `build_retrieval_answer`, `build_compare_answer`, `draft_reply`) now call `build_system_prompt()` before every Ollama request.

3. **Preference echo** — When a user sets a preference, the bot replies with natural language: `"Saved: I'll be more direct with you."` instead of a raw key=value dump.

4. **Debug observability** — Every assembled prompt is logged at DEBUG level — verifiable without a database query.

18/18 tests pass. PERS-01 and PERS-04 requirements met.

## How to Use It

**Set a preference (user-facing):**
1. Tell the bot: "be more direct with me"
2. Bot replies: `"Saved: I'll be more direct with you."`
3. Every subsequent answer now uses a system prompt that includes "be more direct with me"

**Verify it's working (developer):**
```bash
LOG_LEVEL=DEBUG python -m app.main
# Watch for: system_prompt=\n<assembled content>
```

**Run the test suite:**
```bash
pytest tests/ -v
# Expected: 18 passed
```

## Worked Example

**Scenario: User sets a preference, then asks a question**

```
User: use shorter sentences please
Bot:  Saved: I'll use shorter sentences.

User: what's the weather like today?
Bot:  [response in noticeably shorter sentences, because system prompt now includes "use shorter sentences please"]
```

Ollama's `system` parameter on every call now contains:
```
[Base identity]

Behavior preferences:
- use shorter sentences please

Personality traits: none yet
```

**Scenario: No preferences set (fresh user)**
```
Assembled prompt = base SYSTEM_PROMPT only
Personality traits: none yet
(no behavior preferences section)
```

## Tips & Edge Cases

- Extraction calls (`TASK_EXTRACT_PROMPT`, `REMINDER_EXTRACT_PROMPT`, etc.) intentionally do **not** use the dynamic prompt — they need static, structured output and must not be influenced by personality.
- `app/bot/commands.py` still uses the static `SYSTEM_PROMPT` constant — this is out of scope for Phase 2 and will be addressed in a later phase.
- The `personas` section only appears when a persona has `is_active=1`. No active persona = section omitted.
- Preferences survive process restarts (stored in SQLite) — set once, active forever until changed.
