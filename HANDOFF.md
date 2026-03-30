# Tintu Assistant — Handoff

See [PROJECT.md](PROJECT.md) for full goals, decisions, and architecture notes.

*Last updated: 2026-03-30*

---

## Status

**Goal 1 complete. Both bots in production.**

- Dene (Mithu) — live at `/opt/assistant-mithu/`, running as `dene.service`
- Ingle (friend, user ID 5096992323) — live at `/opt/assistant-friend/`, running as `ingle.service`
- VPS: Hetzner CX33, Helsinki, 204.168.209.135
- Model: qwen3:1.7b via Ollama (shared instance, `OLLAMA_KEEP_ALIVE=-1`)

Goal 2 (multi-session Claude via Telegram topics) not started.

---

## What's built and working

### Core assistant
- Natural language routing — intent classifier (keyword + LLM fallback) → handler
- Tasks, reminders, routines, notes, decisions, project tracking
- Vault (Obsidian-compatible Markdown at `BASE_DIR/vault/`)
- SQLite database (`BASE_DIR/data/assistant.db`)
- Scheduled reminder delivery (job queue, checks every 60s)

### Adaptive personality layer
- `personality_traits` table — updated when user shapes tone/style
- `preferences` table — updated from behavioral corrections
- `personas` table — named persona definitions, one active at a time
- `build_system_prompt()` in `app/llm/prompt_builder.py` assembles all layers dynamically each request

### Context management (Phase 3)
- Conversation history stored in DB, loaded on startup
- Session continuity signal on first message (resume/fresh)
- Auto-summarization every 20 turns — sends summary to user for correction
- `conversation_summaries` table stores session summaries

### Commands
- `/start` — onboarding intro with bot name, capabilities, limitations
- `/help` — full command list
- `/profile` — snapshot of everything the bot knows: open tasks, reminders, traits, preferences, vault count, last session summary
- `/task`, `/remind`, `/routine`, `/search`, `/decision`, `/inbox`, `/project`, `/draft`, `/daily`, `/eod`

### LLM client
- Ollama `/api/chat` (not `/api/generate` — bug #14793)
- `think:false` + `/no_think` prefix to suppress chain-of-thought
- `_strip_thinking()` strips any leaked `<think>` blocks
- `num_predict=20` for classification calls (speed)
- `num_thread=4`, response time ~5s on CX33 CPU

---

## Key decisions made

| Decision | Choice | Reason |
|---|---|---|
| Model | qwen3:1.7b | 4b took 2-3 min on CPU; 1.7b under 5s. Quality impact minimal. |
| Ollama endpoint | `/api/chat` | `/api/generate` silently ignores `think:false` (bug #14793) |
| Context budget | 8K working within 32K native | Speed + consistency. Full 32K available if needed. |
| Capability refusal | Hard decline for code/math/research | Clean refusal > confident wrong answer |
| Personality | Dynamic assembly from DB tables | Evolves through natural conversation, not hardcoded |

---

## .env values

**Dene (`/opt/assistant-mithu/.env`)**
```
TELEGRAM_TOKEN=<Mithu's bot token>
TELEGRAM_USER_ID=7912940724
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:1.7b
BASE_DIR=/opt/assistant-mithu
TIMEZONE=Asia/Kolkata
ASSISTANT_NAME=Dene
```

**Ingle (`/opt/assistant-friend/.env`)**
```
TELEGRAM_TOKEN=8726488950:AAEQUZ0qQs3xDU1xVd0myHFPCtk-tMJmJtA
TELEGRAM_USER_ID=5096992323
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:1.7b
BASE_DIR=/opt/assistant-friend
TIMEZONE=Asia/Kolkata
ASSISTANT_NAME=Ingle
```

---

## Key files

| File | Purpose |
|---|---|
| `app/main.py` | Entry point, handler registration |
| `app/config.py` | All config loaded from `.env` |
| `app/bot/commands.py` | All slash command handlers |
| `app/bot/handlers.py` | Natural language message handler |
| `app/bot/router.py` | Intent routing |
| `app/llm/prompt_builder.py` | Assembles dynamic system prompt |
| `app/llm/prompts.py` | `make_system_prompt(name)` + all extraction prompts |
| `app/llm/ollama_client.py` | Ollama API client |
| `app/llm/classifier.py` | Intent classifier |
| `app/storage/models.py` | DB schema |
| `app/storage/migrations.py` | Migration runner |
| `.env.example` | Config template |

---

## VPS operations

```bash
# Status
systemctl status dene
systemctl status ingle
journalctl -u dene -f
journalctl -u ingle -f

# Deploy update
cd /opt/assistant-mithu && git pull && systemctl restart dene
cd /opt/assistant-friend && git pull && systemctl restart ingle

# Ollama
systemctl status ollama
ollama list
```

---

## Open items

- [x] Hetzner CX33 provisioned
- [x] Dene deployed and in production
- [x] Ingle deployed and in production
- [x] Self-evolving system prompt
- [x] `/start` onboarding
- [x] `/profile` summary command
- [ ] Goal 2: multi-session Claude via Telegram group topics — not started
- [ ] Backup script (`scripts/backup.sh`) — not verified running on VPS

---

## Next session starting point

**Goal 2: multi-session Claude via Telegram topics**

Tell Claude: *"Resume Tintu project — Goal 1 is complete, both bots in production. Starting Goal 2: multi-session Claude sessions via a Telegram group with topics. See PROJECT.md Option A."*
