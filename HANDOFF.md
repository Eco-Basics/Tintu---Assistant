# Tintu Assistant — Handoff

See [PROJECT.md](PROJECT.md) for full goals, decisions, and architecture notes.

## Status
Phase 1 + Phase 2 code fully built locally. Ready to deploy. Waiting on Hetzner VPS.

**Scope has expanded since initial build** — adaptive personality layer and context window management need to be added before deployment. Goal 2 (multi-session Claude via TG topics) is a separate build after VPS is up.

---

## What's built

Full Phase 1 + Phase 2 implementation at `C:\Tintu, the Assistant\`

- Telegram bot (natural language only, no slash commands)
- SQLite database with all 8 tables
- Obsidian-compatible Markdown vault
- Ollama client (Qwen3:4b)
- Intent classifier (keyword + LLM fallback)
- Full router handling all intents from plain language:
  - capture note, create task, set reminder, complete task
  - list tasks, create routine, update preference, search
  - retrieval, comparison, daily summary, EOD review, draft
- Scheduled reminder delivery (checks every 60s)
- systemd service file ready

---

## Deployment architecture — two bots, one Ollama

Two completely separate bot deployments on the same VPS. Each has its own
codebase copy, database, vault, and Telegram bot. Both share one Ollama
instance. No code changes required.

```
/opt/
  assistant-mithu/      ← your bot
  assistant-friend/     ← friend's bot
  (ollama runs as a system service, shared)
```

---

## What you need before resuming

1. **Hetzner server** — create at hetzner.com
   - OS: Ubuntu 24.04
   - Type: CX33 (4 vCPU, 8GB RAM)
   - Note the IP address and root password from the email

2. **Your Telegram bot token** — you already have this

3. **Your Telegram user ID** — `7912940724`

4. **Friend's Telegram bot** — your friend creates a new bot via [@BotFather](https://t.me/BotFather)
   - Send `/newbot`, follow prompts, copy the token
   - Friend gets their user ID from [@userinfobot](https://t.me/userinfobot)

---

## Resume instructions

Tell Claude: *"Resume the Tintu two-bot deployment — Hetzner is set up, IP is X.X.X.X"*

### Steps (done once, for both bots)

**Server setup**
1. SSH into the server
2. Install Python 3.11+, pip, venv
3. Install Ollama and pull `qwen3:4b`
4. Create system user: `useradd -r -s /bin/false assistant`

**Deploy your bot**
1. Upload code to `/opt/assistant-mithu/`
2. Create venv: `python3 -m venv /opt/assistant-mithu/venv`
3. Install deps: `venv/bin/pip install -r requirements.txt`
4. Create `.env` (see values below — Mithu)
5. Test manually: `venv/bin/python -m app.main`
6. Install service: copy `systemd/assistant-mithu.service` to `/etc/systemd/system/`
7. `systemctl enable --now assistant-mithu`

**Deploy friend's bot**
1. Upload same code to `/opt/assistant-friend/`
2. Create venv: `python3 -m venv /opt/assistant-friend/venv`
3. Install deps: `venv/bin/pip install -r requirements.txt`
4. Create `.env` (see values below — Friend)
5. Test manually: `venv/bin/python -m app.main`
6. Install service: copy `systemd/assistant-friend.service` to `/etc/systemd/system/`
7. `systemctl enable --now assistant-friend`

---

## Key files

| File | Purpose |
|---|---|
| `app/main.py` | Entry point |
| `app/config.py` | All config loaded from `.env` |
| `.env.example` | Template — copy to `.env` and fill in |
| `systemd/assistant-mithu.service` | systemd service for your bot |
| `systemd/assistant-friend.service` | systemd service for friend's bot |
| `scripts/backup.sh` | Daily backup of DB + vault |

---

## .env values — Mithu (`/opt/assistant-mithu/.env`)

```
TELEGRAM_TOKEN=<your bot token>
TELEGRAM_USER_ID=7912940724
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
BASE_DIR=/opt/assistant-mithu
TIMEZONE=Asia/Kolkata
```

## .env values — Friend (`/opt/assistant-friend/.env`)

```
TELEGRAM_TOKEN=<friend's bot token>
TELEGRAM_USER_ID=<friend's telegram user ID>
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
BASE_DIR=/opt/assistant-friend
TIMEZONE=<friend's timezone>
```
