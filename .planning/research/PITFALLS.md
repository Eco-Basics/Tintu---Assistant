# Pitfalls Research

**Domain:** Adaptive AI assistant — persistent personality, context budget management, multi-session subprocess orchestration on a resource-constrained VPS
**Researched:** 2026-03-27
**Confidence:** HIGH (derived from direct codebase analysis + domain knowledge of LLM context management patterns)

---

## Critical Pitfalls

### Pitfall 1: Personality Stored But Never Injected

**What goes wrong:**
Personality traits and behavior preferences are saved to the `preferences` table correctly, but when the dynamic system prompt is assembled, the code either reads an empty result set (wrong query), reads preferences in the wrong format, or caps them at a token limit that silently truncates them to nothing. The LLM receives the static fallback system prompt, ignores all preferences the user ever stated, and the user sees no difference from before the feature shipped.

**Why it happens:**
The existing `SYSTEM_PROMPT` in `app/llm/prompts.py` is a hard-coded string. Building the dynamic replacement requires assembling a prompt from DB rows at request time. Developers typically test the happy path (one preference, short value) and miss the failure path (zero rows returned, or rows returned but assembled string is malformed). Because Qwen3:4b's responses are variable, personality drift is plausible even on working prompts — making silent injection failure easy to mistake for model behaviour.

**How to avoid:**
- The system prompt assembler must log the assembled string (at DEBUG level) on every call — this makes injection failures immediately visible in logs.
- Add an explicit guard: if zero personality rows are found, log a WARNING and use the static fallback. Do not silently fall back without logging.
- Write a unit test that mocks DB rows and asserts the assembled prompt contains the expected preference values.
- The context budget manager must allocate a minimum slot for personality (e.g., 200 tokens guaranteed) before allocating anything else.

**Warning signs:**
- User states a preference, confirms it saved, but assistant behaviour is unchanged in the next message.
- `preferences` table has rows but the assembled system prompt in logs is identical to the static SYSTEM_PROMPT.
- The `update_preference` intent returns success but the subsequent `answer` intent uses the static fallback path in `response_builder.py`.

**Phase to address:** Adaptive personality layer (Goal 1) — specifically the dynamic system prompt assembly step.

---

### Pitfall 2: Context Budget Miscalculation Causes Silent Window Overflow

**What goes wrong:**
The budget manager estimates token counts using a character-ratio heuristic (e.g., `len(text) / 4`). Qwen3:4b uses a different tokeniser than GPT models. The estimate is systematically off — typically undercounting CJK characters and overly structured text (bullet lists, code, JSON). The assembled prompt exceeds 8192 tokens. Ollama silently truncates from the start of the context, cutting conversation history or the system prompt entirely. The model responds as if it has no memory and no personality, with no error raised.

**Why it happens:**
Ollama's `/api/generate` endpoint does not return an error when the prompt exceeds the model's context window — it silently clips. There is no built-in token counter for Qwen3:4b in Python without loading the full tokeniser. Developers assume a per-character estimate is good enough and don't test with prompts near the limit.

**How to avoid:**
- Use `transformers.AutoTokenizer` for Qwen3:4b offline token counting — it is accurate. Load the tokeniser once at startup and expose a `count_tokens(text: str) -> int` utility. Do not use `len(text) / 4`.
- Alternatively, use Ollama's `/api/show` response which exposes `num_ctx` and query `/api/generate` with `options.num_ctx` explicitly set. After each call, check `eval_count` + `prompt_eval_count` in the response JSON — if `prompt_eval_count` is less than the expected prompt token count, truncation occurred.
- Enforce hard slot limits before assembly: system prompt ≤ 600 tokens, active tasks ≤ 300 tokens, retrieved memory ≤ 500 tokens, conversation history ≤ 6000 tokens (leave 500 for output). Trim conversation history first (oldest turns), then retrieved memory, never the system prompt.
- Log assembled prompt token count on every request. Alert if count exceeds 7500.

**Warning signs:**
- Assistant "forgets" preferences mid-conversation even when the personality layer is working.
- `prompt_eval_count` in Ollama response JSON is suspiciously low compared to what was sent.
- Responses become shorter and less contextual as conversation grows.
- Memory retrieval answers seem correct but ignore the specific question phrasing.

**Phase to address:** Context budget manager implementation — must be built before personality layer is tested at scale.

---

### Pitfall 3: Session Summarization Loses Actionable Context

**What goes wrong:**
The existing `summarize_conversation()` in `app/memory/summarizer.py` asks Qwen3:4b to produce a five-field structured summary. Qwen3:4b at 4b parameters produces summaries that capture topics but drop specifics: exact task titles, decision outcomes, quoted preferences, and named entities (project names, people) get paraphrased into vague categories. The next session retrieval finds the summary but cannot reconstruct the specifics that mattered. The user says "remember when I decided X" and the assistant correctly says "yes, you made a decision about X" but cannot recall the actual decision.

**Why it happens:**
The SUMMARIZE_PROMPT asks for a "concise" one-paragraph summary — which the model correctly interprets as "generalise". There is no instruction to preserve verbatim key facts. Additionally, the summary is stored as free text and retrieved only when the summary itself fuzzy-matches the query — if the user asks about a project name not in the summary text, the row won't be returned.

**How to avoid:**
- Restructure the summary prompt to produce two sections: a narrative paragraph AND a verbatim key-facts list (task titles, decisions verbatim, preference changes verbatim, project names mentioned). Store the key-facts list as a separate `key_facts TEXT` column.
- Add a `named_entities TEXT` column to `conversation_summaries` for project names and people names — index these for retrieval.
- During retrieval, query `key_facts` and `named_entities` columns separately in addition to `summary`. This makes specific-fact retrieval much more reliable.
- After summarization, immediately verify the summary contains at least N key facts if N tasks/decisions were in the source log. If not, re-run with a stricter prompt.

**Warning signs:**
- Summary stored in DB contains only generic phrases like "user discussed project planning" with no project names.
- The `topics` field is populated but `actions` and `decisions` fields are empty or contain "none" despite the source log having explicit decisions.
- User complaint: "you don't remember what I actually decided, just that I made a decision."

**Phase to address:** Session summarization — after context budget manager, before rolling compression is enabled.

---

### Pitfall 4: Claude CLI Subprocess Leaks on VPS

**What goes wrong:**
Each Telegram topic message spawns or resumes a `claude` CLI subprocess. On error (network drop, message parse failure, exception in the Python handler), the subprocess is not terminated. On VPS restart without cleanup, orphaned `claude` processes accumulate. With 4-5 active project topics and 1-2 leaked processes each, the VPS reaches 6+ `claude` processes consuming 300-500MB each. Combined with two Ollama bot processes and Ollama itself (~2-3GB for Qwen3:4b), the CX33's 8GB RAM is exhausted and the OOM killer terminates Ollama, taking both assistants offline.

**Why it happens:**
Python `subprocess.Popen` does not auto-terminate child processes when the parent handler function raises an exception. The `claude` CLI does not self-terminate when stdin closes if it is in interactive/REPL mode. Developers test with one topic and a clean exit path, missing the failure path.

**How to avoid:**
- Use a process registry: a module-level `dict[topic_id, subprocess.Popen]` that tracks exactly one process per topic. Before spawning, check the registry. If a process exists and is alive (`poll() is None`), reuse it. If it is dead, clean the entry and respawn.
- Wrap all subprocess send/receive in a try/finally that sets a maximum message timeout (30s). On timeout or exception, terminate the process, remove it from the registry, and report an error to the user.
- Add a health check job (every 5 minutes) that iterates the registry, terminates any process with `poll() is not None`, and logs the count of active processes.
- Set a hard cap: maximum 4 concurrent Claude processes. If a 5th is requested, return an error explaining the limit.
- On bot shutdown (`SIGTERM`), iterate the registry and call `proc.terminate()` for every entry before exiting.

**Warning signs:**
- `ps aux | grep claude` shows more processes than active topics.
- VPS memory usage climbs steadily without conversation activity.
- OOM killer log entries in `journalctl`.
- New topic messages get no response because the bot process itself was killed.

**Phase to address:** Multi-session Claude subprocess management (Goal 2) — process registry must be the first thing built, before any message routing.

---

### Pitfall 5: Telegram Topic Routing Sends Messages to the Wrong Session

**What goes wrong:**
The bot receives a message from a Telegram group topic. The `message_thread_id` attribute on the `Update` object identifies which topic it came from. If the routing layer uses `chat_id` instead of `(chat_id, message_thread_id)` as the session key, all topics in the same group map to the same Claude process. Project A messages get routed to Project B's Claude session. Context bleeds across projects.

**Why it happens:**
`python-telegram-bot` exposes `update.effective_message.message_thread_id` only for messages in Forum/Topics mode. In testing with a regular group or DM, `message_thread_id` is `None`. Developers test routing without Forum mode enabled and the `None` key works fine — the bug only appears in production with topics.

**How to avoid:**
- The session key must always be `(chat_id, message_thread_id)`. Never use `chat_id` alone for the Goal 2 bot.
- Add a startup assertion: if the bot receives a message from a group but `message_thread_id is None`, log a hard WARNING and refuse to route — this indicates Forum mode is not enabled on the group.
- Write a test that constructs a mock `Update` with `message_thread_id=42` and verifies the router selects the correct session.
- When creating a new project topic, explicitly validate that the group has Forum mode enabled before writing the topic ID to configuration.

**Warning signs:**
- Both project topics return responses, but the responses reference the other project's context.
- `message_thread_id` logged as `None` for group messages.
- The process registry has only one entry despite multiple topics being active.

**Phase to address:** Telegram topic routing setup — the first integration test before any Claude subprocess work.

---

### Pitfall 6: Qwen3:4b Capability Hallucination Is Hard to Intercept

**What goes wrong:**
The intent router classifies a message as `answer` and calls `build_answer()`, which calls `generate(message, system=SYSTEM_PROMPT)` with no capability guard. Qwen3:4b confidently answers a coding question, produces plausible-looking but incorrect Python, and the user acts on it. The capability refusal system (planned for Goal 1) is never reached because the refusal logic needs to sit in the request path before `generate()` is called, but the current architecture has `build_answer()` call `generate()` directly.

**Why it happens:**
The refusal logic is easiest to bolt on as a post-processing step ("if response contains code, prepend disclaimer") but this is the wrong place — the model has already generated the output. The correct intercept is a pre-generation capability classifier that checks the message before any LLM call. Developers add it after the router, which means capability-matched messages still reach Qwen3:4b.

**How to avoid:**
- Add a synchronous keyword-first capability check in `route()` before the intent classifier. This check looks for code/math/research signals in the raw message text and returns a canned refusal string without any LLM call.
- The keyword check should cover: code patterns (``` backtick blocks, "write a function", "debug this", "explain this code"), math patterns ("calculate", "solve for", "integral", "derivative"), research patterns ("what is the latest", "current events", "as of today"), and external-data patterns ("check the price", "what is the weather").
- The LLM-based fallback capability check (for edge cases the keyword filter misses) must also sit before `generate()` in `build_answer()`, not after.
- Log every triggered refusal with the original message for later analysis — this builds a corpus for expanding the keyword list.

**Warning signs:**
- User reports getting plausible-looking but wrong code or math answers.
- Refusal strings appear in responses for some messages but not for similar messages phrased differently.
- The `answer` intent is responsible for an unexpectedly high share of responses (check message_log table).

**Phase to address:** Capability refusal system — must be in place before any user-facing testing of the personality layer.

---

### Pitfall 7: Preference Extraction Overwrites With Inferred Noise

**What goes wrong:**
The `update_preference` intent triggers on casual conversational statements that weren't intended as preference commands. "I usually wake up at 7" gets extracted as `key=morning_wakeup_time, value=07:00` and persists. Later, the dynamic system prompt injects this as a personality trait. More critically, `ON CONFLICT(key) DO UPDATE` in the existing DB schema means a later casual statement about a one-off schedule overwrites the real preference the user explicitly set.

**Why it happens:**
The `PREFERENCE_EXTRACT_PROMPT` asks Qwen3:4b to extract a preference from "the following message" — the model is instructed to find a preference regardless of whether one was intended. The intent classifier may also misfire: a statement like "I like to keep things brief" intended as conversational context gets classified as `update_preference`.

**How to avoid:**
- Add a confidence gate: after extracting key/value, ask the model a second question: "Did the user explicitly intend to set this as a persistent preference, or is this a casual statement?" Only persist if the model returns YES with high confidence.
- Alternatively, require explicit confirmation: when `update_preference` triggers, echo back "I'll remember: [key] = [value]. Is that right?" and only write on confirmation.
- Add a `confidence` column to the `preferences` table (high/medium/inferred). Only inject high/medium confidence preferences into the system prompt. Inferred ones can be visible to the user but don't affect personality.
- Allow explicit deletion: "forget that I said X" must be a handled intent.

**Warning signs:**
- `preferences` table accumulates many rows with keys the user never explicitly set.
- `source` field shows conversational statements ("I usually...") rather than direct commands.
- System prompt grows steadily with low-quality preferences injected into the personality slot.

**Phase to address:** Preference extraction — during personality layer implementation, before session summarization.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hard-coded `SYSTEM_PROMPT` string in `prompts.py` | No DB dependency on every request | Cannot evolve personality without code deploy; personality layer cannot be built on top of it | Never — must be replaced by dynamic assembly before Goal 1 |
| `len(text) / 4` for token estimation | Zero dependencies | Systematic undercounting leads to context overflow for non-English text and structured output | Never for production; acceptable only in unit tests with known ASCII input |
| `_parse_kv()` for LLM structured output | Simple to implement | LLM may return extra explanation lines that corrupt parsing; fallback values mask failures silently | Only if all extraction prompts instruct the model to return ONLY the format with no preamble |
| No conversation history in prompt | Keeps current prompts clean and under token budget | User must repeat context in every message; multi-turn reasoning impossible | Acceptable in V1 but blocks the personality layer from being useful |
| `execute()` / `fetchall()` opening a new DB connection per call | Simple, no pooling logic | 5-10ms overhead per query; contention possible with two bots sharing one SQLite file | Acceptable while CX33 is the only deployment target and message volume is 1 user |
| `subprocess.Popen` without process registry | Fast to implement one topic | Subprocess leaks on any exception; OOM risk on shared VPS | Never — process registry must exist before any subprocess is created |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Ollama `/api/generate` | Assuming context overflow raises an error | It does not — Ollama silently truncates. Check `prompt_eval_count` in the response body after every call. |
| Ollama `/api/generate` | Not setting `options.num_ctx` explicitly | Ollama defaults to whatever `num_ctx` the model was loaded with, which may be 2048 not 8192. Always pass `"options": {"num_ctx": 8192}` in the payload. |
| Telegram Forum topics | Using `update.effective_chat.id` as session key | Must use `(chat_id, message_thread_id)` tuple. `message_thread_id` is `None` in non-topic mode, causing all topics to collide on a single key. |
| Telegram Forum topics | Sending replies without `message_thread_id` | Reply will land in the General topic, not the project topic. Always pass `message_thread_id` to `reply_text()` in Goal 2. |
| `claude` CLI subprocess | Reading stdout with `communicate()` | `communicate()` waits for EOF — `claude` CLI never closes stdout in interactive mode. Use `readline()` in a loop with a timeout. |
| `claude` CLI subprocess | Expecting zero exit code on success | Claude CLI may return non-zero on partial failures while still producing output. Check output presence, not just exit code. |
| `aiosqlite` with two bot processes | Assuming WAL mode prevents contention | WAL reduces write contention but two processes writing simultaneously can still produce `database is locked` errors. Implement retry with exponential backoff for write operations. |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full vault scan on every retrieval | Search latency 1-2s for 500+ notes | Add SQLite FTS5 table indexed on vault content, updated on write | ~300 notes (already approaching this threshold per CONCERNS.md) |
| No conversation history in prompt means no multi-turn context | Each Ollama call is isolated; user must repeat context | Build context budget manager that includes rolling last N turns | Day one of personality testing — immediately obvious |
| Two Ollama bots on one CX33 + Qwen3:4b model | Model loaded once but inference is serial; second bot queues behind first | Acceptable for now — Ollama handles queuing. Becomes a problem if both users are active simultaneously | >3 concurrent requests; ~5s queue delay per message |
| DB connection per operation with two processes | Occasional `database is locked` errors under concurrent write | Retry with backoff (3 attempts, 100ms/200ms/400ms) | Two bots writing reminders simultaneously during the 60s reminder check |
| Building dynamic system prompt with `SELECT *` from preferences | Prompt grows unboundedly as preferences accumulate | Cap at top 10 most recent/highest-confidence preferences; enforce token slot limit | After ~50 preferences (several months of use) |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Personality preferences stored as plain text and injected verbatim into system prompt | Prompt injection: user sends "ignore previous instructions and..." as a preference value; it gets persisted and injected on every future call | Strip or escape angle brackets and instruction-like patterns from preference values before storage; never inject raw user input verbatim as system-level instructions |
| Claude CLI subprocess inherits full parent environment | VPS environment variables (Telegram tokens, DB paths) visible to `claude` subprocess via `/proc/self/environ` on Linux | Spawn Claude with a scrubbed environment: pass only `HOME`, `PATH`, `CLAUDE_*` variables; use `env={}` with explicit whitelist in `subprocess.Popen` |
| `message_log` stores first 200 chars of every message unencrypted | Personal data in plaintext SQLite on VPS | Document this is intentional single-user design; add backup encryption (already flagged in CONCERNS.md) |
| No rate limiting on the Telegram filter | Compromised Telegram account generates unlimited LLM inference load on VPS | Add per-message rate limit: max 30 messages per 5 minutes; return error and log when exceeded |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Capability refusal is abrupt with no guidance | User gets "I can't do that" with no direction; frustration | Refusal message should state what alternatives exist: "I can't write code, but I can note this as a task for a coding session in Claude." |
| Preference changes confirmed but not echoed back | User unsure what was actually stored; may set conflicting preferences | After writing a preference, always echo: "Saved: I'll [natural language description of what this changes]" |
| Session summarization happens silently | User doesn't know their conversation was compressed; next session feels like amnesia | On first message of a new session, if a prior-session summary is being loaded via retrieval, say so: "Starting fresh — I have a summary of our last session if you need it." |
| Topic routing sends Claude's full output including markdown/code blocks | Telegram messages with unrendered markdown look cluttered | For Goal 2, detect when Claude output contains code blocks and send as a file or use `parse_mode=None` for raw text delivery |
| Qwen3:4b adds "Think" tokens in reasoning mode | User sees internal deliberation ` <think>...</think>` blocks in responses | Strip `<think>...</think>` blocks from all Qwen3:4b responses before sending to Telegram |

---

## "Looks Done But Isn't" Checklist

- [ ] **Dynamic system prompt:** Preferences are being read from DB — verify assembled prompt is actually different from the static fallback by logging it on first request.
- [ ] **Context budget manager:** Token counts are logged per slot — verify sum does not exceed 7,500 before any Ollama call.
- [ ] **Session summarization trigger:** Verify the 20-turn threshold actually fires — check `conversation_summaries` table has rows after 20 messages.
- [ ] **Rolling compression:** After compression, verify conversation history in the next Ollama call contains the summary, not the original 20 turns.
- [ ] **Claude subprocess registry:** After two topics are active, verify `ps aux | grep claude` shows exactly 2 processes, not 4 or 6.
- [ ] **Topic routing:** Send a message to Topic A and verify Claude's response references Topic A's project directory, not Topic B's.
- [ ] **Capability refusal:** Send "write me a Python function to sort a list" — verify it is refused without any LLM call.
- [ ] **Ollama num_ctx:** After sending a long message, check `prompt_eval_count` in Ollama response matches the expected token count, confirming `num_ctx=8192` is active.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Personality not being injected | LOW | Add logging to assembler, redeploy; no data loss |
| Context overflow causing amnesia | LOW | Fix budget manager, redeploy; existing summaries are still valid |
| Summarization producing poor quality | MEDIUM | Re-run summarization on stored `message_log` rows with improved prompt; summaries are regenerable from source |
| Subprocess leaks / OOM | MEDIUM | `systemctl restart assistant-*`; `pkill -f claude`; add process registry before next deployment |
| Topic routing collision (wrong session gets messages) | HIGH | Messages sent to wrong Claude session may corrupt that session's context; reset the affected Claude session's history file and start fresh for that project |
| Preference overwrite with noise | LOW | Query `preferences` table, identify low-confidence rows by `source` text, delete them; add confidence column in migration |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Personality not injected | Dynamic system prompt assembly | Log assembled prompt; confirm it differs from static fallback |
| Context overflow (silent Ollama truncation) | Context budget manager | Check `prompt_eval_count` in Ollama response after every call |
| Summarization loses specifics | Session summarization redesign | Inspect `key_facts` column in `conversation_summaries` after 20-turn test |
| Subprocess leaks on VPS | Process registry implementation (Goal 2, first step) | `ps aux | grep claude` count equals active topic count after error injection |
| Topic routing collision | Telegram Forum routing setup | Send to each topic, verify session isolation in process registry |
| Qwen capability hallucination | Capability refusal (before personality testing) | Send code/math/research prompts; verify no LLM call is made |
| Preference noise overwrite | Preference extraction confidence gate | Inspect `preferences` table after casual conversation; no unintended rows |

---

## Sources

- Direct codebase analysis: `app/llm/ollama_client.py`, `app/llm/prompts.py`, `app/memory/summarizer.py`, `app/bot/router.py`, `app/storage/models.py`, `app/storage/db.py`, `app/memory/retrieval.py`, `app/llm/response_builder.py`
- `.planning/codebase/CONCERNS.md` — known issues and fragile areas audit (2026-03-27)
- `.planning/PROJECT.md` — constraints, goals, and key decisions
- Ollama API behaviour (silent truncation, `prompt_eval_count` field) — verified from Ollama API documentation patterns and known model serving behaviour
- `python-telegram-bot` v21.3 Forum topics behaviour — `message_thread_id` field semantics from library documentation

---
*Pitfalls research for: Adaptive AI assistant — persistent personality, context budget, subprocess orchestration*
*Researched: 2026-03-27*
