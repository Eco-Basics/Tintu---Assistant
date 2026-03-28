# Technology Stack

**Project:** Tintu — Personal AI Assistant Platform
**Researched:** 2026-03-28
**Overall confidence:** HIGH (existing code inspected directly; Ollama and Claude CLI behavior verified against official docs and GitHub issues)

---

## Verdict on Existing Stack

The existing codebase is sound. No replacements are needed. The choices below are all keep or supplement decisions.

| Component | Verdict | Rationale |
|-----------|---------|-----------|
| `python-telegram-bot[job-queue]==21.3` | **Keep** | Stable async PTB with APScheduler-backed JobQueue; correct version |
| `httpx==0.27.0` | **Replace with `aiohttp`** | See note below — httpx is fine but aiohttp is already the pattern used in the codebase description; actual code uses httpx. Either works; httpx is the current choice and is fine to keep. |
| `aiosqlite==0.20.0` | **Keep** | Correct async SQLite wrapper; WAL already enabled in `db.py` |
| `python-dotenv==1.0.1` | **Keep** | Appropriate for per-deployment `.env` files |
| `systemd service files` | **Keep, supplement** | Correct structure; add resource limits (see below) |

**Note on httpx vs aiohttp:** The codebase uses `httpx` (not `aiohttp` as the project description implies). Both are async-capable and both work correctly for Ollama HTTP calls. `httpx` has a simpler API for one-off async requests; `aiohttp` is marginally faster for high-concurrency throughput but that difference is irrelevant here (two bots, low message volume). Keep `httpx` — no justification to switch.

---

## Recommended Additions

### Goal 1: Adaptive personality layer

| Library | Version | Purpose | Rationale |
|---------|---------|---------|-----------|
| `tiktoken` | latest | Token counting for context budget management | Fast BPE tokenizer from OpenAI; works well for estimating token budgets even for Qwen3 (Qwen uses a compatible BPE tokenizer). Alternative: use Ollama's `/api/show` to get context length, then estimate from character count at ~4 chars/token. `tiktoken` is more precise. |

No other additions required for Goal 1.

### Goal 2: Claude CLI subprocess management

| Library | Version | Purpose | Rationale |
|---------|---------|---------|-----------|
| `asyncio` (stdlib) | — | Spawn and manage `claude` subprocesses | `asyncio.create_subprocess_exec` is the right tool; see subprocess section below |

No additional third-party packages needed for subprocess management.

---

## Full Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Implementation language | Already decided; 3.11 has `asyncio` improvements relevant to subprocess management |
| `python-telegram-bot[job-queue]` | 21.3 | Telegram bot + scheduled reminders | Async-native; JobQueue wraps APScheduler correctly for in-process scheduling |
| `httpx` | 0.27.0 | Ollama HTTP client | Async-capable, simple API, already in use |
| `aiosqlite` | 0.20.0 | Async SQLite access | Wraps sqlite3 in a dedicated thread; prevents event loop blocking |
| `python-dotenv` | 1.0.1 | Environment config per deployment | Clean separation of secrets from code |

### Inference

| Technology | Purpose | Why |
|------------|---------|-----|
| Ollama (system service) | Serve Qwen3:4b | Local inference, no API keys, both bots share one instance |
| Qwen3:4b (Q4_K_M quantization) | Conversational AI | ~2.5GB model weight on disk; ~3-4GB RAM at runtime; fits comfortably in 8GB VPS |

### Storage

| Technology | Purpose | Why |
|------------|---------|-----|
| SQLite via `aiosqlite` | Per-bot structured data | Zero-dependency, no separate service, WAL mode handles the async access pattern |
| Markdown files (vault) | Memory store, Obsidian-compatible | Plain files, easy to backup, git-trackable if desired |

### Infrastructure

| Technology | Purpose | Why |
|------------|---------|-----|
| systemd | Service lifecycle | Already written; correct for persistent VPS services |
| `rsync` over SSH | Code deployment | Sufficient for a two-service personal project; no CI/CD overhead |

---

## Subprocess Management for Claude CLI (Goal 2)

### The right approach: `asyncio.create_subprocess_exec` + `--resume`

The Claude CLI supports two modes relevant here:

**One-shot per message (`-p` / `--print` flag):**
```bash
claude -p "your prompt" --resume <session_id> --output-format json
```
Each Telegram message spawns one `claude -p` invocation. The `--resume <session_id>` flag continues the conversation for that topic. The process exits after printing the response as JSON to stdout. Clean, predictable, no zombie processes.

**Why not a long-lived subprocess per topic:**
A persistent subprocess with stdin/stdout pipe is possible but creates failure surface: the process can stall, the pipe buffer can fill, and teardown on Telegram disconnect is unreliable. For a Telegram bot, message latency is already ~seconds; the overhead of spawning a new process per message is negligible compared to Claude's inference time.

### Implementation pattern

```python
import asyncio
import json

async def ask_claude(prompt: str, session_id: str | None, cwd: str) -> tuple[str, str]:
    """
    Returns (response_text, new_session_id).
    cwd is the project directory for this topic.
    """
    args = ["claude", "-p", prompt, "--output-format", "json"]
    if session_id:
        args += ["--resume", session_id]

    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=300,  # 5 minute ceiling
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise

    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {stderr.decode()}")

    data = json.loads(stdout.decode())
    return data["result"], data["session_id"]
```

Key decisions in this pattern:

- `create_subprocess_exec` (not `create_subprocess_shell`) — no shell injection surface, more predictable behavior
- `communicate()` (not manual `read`/`write`) — avoids pipe deadlocks; this is the Python docs recommendation
- `asyncio.wait_for` with timeout — Claude inference can stall; the bot must not hang indefinitely
- `proc.kill()` + `await proc.wait()` on timeout — ensures no orphan processes; the `wait()` reaps the zombie
- `--output-format json` — structured output with `session_id` field, no text parsing needed
- `cwd` set to project directory — Claude picks up `.claude/` history from the correct location

### Session ID persistence

Store `session_id` per topic in a small SQLite table (separate from the personal assistant DBs):

```sql
CREATE TABLE claude_sessions (
    topic_id   TEXT PRIMARY KEY,   -- Telegram thread_id as string
    session_id TEXT NOT NULL,
    project_dir TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);
```

On first message in a topic: no `--resume`, capture returned `session_id`, insert row.
On subsequent messages: load `session_id`, pass `--resume`, update row with new `session_id`.

### Concurrency cap

Hard cap at 4 concurrent Claude processes (as decided). Implement with `asyncio.Semaphore(4)`. If a 5th request arrives, the bot replies "Another task is running in this session. Send your message again when it completes." Do not queue silently — the user needs to know.

### Known issues

- **Empty output on large stdin** (GitHub issue #7263): Occurs when piping large content via stdin in `-p` mode. Not relevant here since prompts come from Telegram messages (short). If attaching file content, chunk it or write to a temp file and reference by path.
- **`--bare` flag**: Recommended in official docs for scripted calls to skip OAuth/keychain/hook loading. For Goal 2 this is NOT appropriate — the user needs their OAuth session and project `.claude/` config to persist. Do not use `--bare`.

---

## Ollama Concurrency Behavior

**Setup:** Two bot processes, one Ollama instance at `http://localhost:11434`, serving `qwen3:4b`.

**How Ollama handles concurrent requests (verified against Ollama FAQ and GitHub issues):**

1. `OLLAMA_NUM_PARALLEL` defaults to auto-select: 4 if memory allows, 1 if not. On an 8GB VPS with Qwen3:4b (~3-4GB RAM for the model), there is limited headroom for parallel contexts. Ollama will likely default to `OLLAMA_NUM_PARALLEL=1` due to memory constraints.

2. When `OLLAMA_NUM_PARALLEL=1`, a second request arriving while the first is processing is queued (FIFO). The queue default holds up to 512 requests (`OLLAMA_MAX_QUEUE`). There is no 503 error unless the queue overflows.

3. **Practical consequence for two bots:** If Mithu and Friend send messages at the exact same second, one waits in Ollama's internal queue. Given the conversational nature of the use case (not a high-throughput API), this is acceptable. Typical latency adds ~5-15 seconds per queued request on CPU.

**Recommendation:** Set `OLLAMA_NUM_PARALLEL=1` explicitly in the Ollama systemd service environment to prevent Ollama from attempting parallel inference and unexpectedly blowing past the memory budget:

```ini
# /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
```

`OLLAMA_MAX_LOADED_MODELS=1` prevents Ollama from loading a second model if someone experiments later. With 8GB RAM split between two bot processes, Ollama, and system overhead, there is no room for two loaded models.

**Memory budget estimate for CX33 (8GB RAM):**

| Component | RAM estimate |
|-----------|-------------|
| Qwen3:4b (Q4_K_M, loaded by Ollama) | ~3.5 GB |
| Ollama server overhead | ~200 MB |
| assistant-mithu bot process | ~80 MB |
| assistant-friend bot process | ~80 MB |
| Ubuntu 24.04 system | ~400 MB |
| KV cache (1 parallel slot, 8k context) | ~400 MB |
| **Total** | ~4.7 GB |
| **Headroom** | ~3.3 GB |

Headroom is adequate. The 8GB limit is not a risk under normal operation.

---

## SQLite Isolation Confirmation

**Each bot has a completely separate database file** at its own `BASE_DIR/data/assistant.db`. These files never interact.

SQLite's documented behavior confirms this is sound:
- Two processes accessing different database files have zero interaction at the SQLite layer.
- WAL mode (already enabled in `db.py` via `PRAGMA journal_mode=WAL`) is the recommended mode for any concurrent access within a single process. For a single-writer async bot, WAL also reduces lock contention on reads during writes.
- `aiosqlite` serializes all operations on a single SQLite connection through an internal thread queue, which is the correct async pattern for SQLite.

**One concern in the current `db.py`:** Each helper function (`fetchone`, `fetchall`, `execute`) opens a fresh connection and closes it. This is correct for safety but means WAL mode must be re-enabled on every connection. The existing code does this correctly — `PRAGMA journal_mode=WAL` runs in `get_db()` before any query. No change needed.

**Not recommended:** Sharing a single SQLite database between two bots. The current isolated-database design is correct and should not be changed.

---

## systemd Service Configuration

### Existing service files: what to add

The existing `assistant-mithu.service` is correctly structured. Add resource limits to protect the VPS from a runaway bot process:

```ini
[Unit]
Description=Tintu Assistant Bot — Mithu
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=assistant
WorkingDirectory=/opt/assistant-mithu
ExecStart=/opt/assistant-mithu/venv/bin/python -m app.main
Restart=on-failure
RestartSec=10
EnvironmentFile=/opt/assistant-mithu/.env

# Resource limits
MemoryMax=512M
MemoryHigh=400M
CPUQuota=100%

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

`MemoryMax=512M` — hard ceiling; triggers OOM killer for that process only if exceeded. Python bots are typically 60-100MB; 512MB is generous headroom for spikes.
`MemoryHigh=400M` — soft ceiling; systemd throttles allocation before hard limit.
`CPUQuota=100%` — allows full use of one CPU core but prevents monopolizing all 4.

Apply identical limits to `assistant-friend.service`.

### Ollama service ordering

The existing `After=network.target ollama.service` and `Wants=ollama.service` are correct. systemd will start Ollama before the bot, and if Ollama is not running the bot starts anyway (Wants, not Requires). The `check_ollama()` function in `ollama_client.py` handles the case where Ollama is temporarily unavailable.

### Service for Goal 2 (Claude bot)

A third service for the Claude routing bot should follow the same pattern. Add `After=network.target` (no Ollama dependency). The `claude` CLI process is spawned per-request, not as a persistent service.

### Restart policy

`Restart=on-failure` with `RestartSec=10` is appropriate for all three services. Do not use `Restart=always` — if a bot crashes immediately on startup (e.g., bad `.env`), `always` causes a restart loop that floods the journal.

---

## Deployment Workflow

### Recommended: `rsync` over SSH with a deploy script

No CI/CD is appropriate here. The deploy workflow is:

```bash
#!/bin/bash
# deploy.sh — run from local machine
# Usage: ./deploy.sh <server_ip> <bot_name>
# Example: ./deploy.sh 1.2.3.4 mithu

SERVER=$1
BOT=$2
REMOTE_DIR="/opt/assistant-$BOT"

# Sync code (exclude secrets, venv, data)
rsync -avz --delete \
  --exclude '.env' \
  --exclude 'venv/' \
  --exclude 'data/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.git/' \
  ./app/ $SERVER:$REMOTE_DIR/app/
rsync -avz ./requirements.txt $SERVER:$REMOTE_DIR/
rsync -avz ./prompts/ $SERVER:$REMOTE_DIR/prompts/
rsync -avz ./systemd/ $SERVER:$REMOTE_DIR/systemd/

# Restart the service
ssh $SERVER "systemctl restart assistant-$BOT"
echo "Deployed to $BOT. Check: ssh $SERVER journalctl -u assistant-$BOT -f"
```

Key decisions:
- `--exclude '.env'` — never overwrite secrets on the server
- `--exclude 'data/'` — never overwrite the live database with local files
- `--exclude 'venv/'` — venv lives on the server; only sync code
- `--delete` — removes files deleted locally from the server

### Initial deployment (one-time)

```bash
# 1. Upload code and create venv
rsync -avz ./ user@server:/opt/assistant-mithu/ --exclude .env
ssh user@server "cd /opt/assistant-mithu && python3 -m venv venv && venv/bin/pip install -r requirements.txt"

# 2. Create .env manually on server (never rsync secrets)
ssh user@server "nano /opt/assistant-mithu/.env"

# 3. Install and start service
ssh user@server "cp /opt/assistant-mithu/systemd/assistant-mithu.service /etc/systemd/system/ && systemctl daemon-reload && systemctl enable --now assistant-mithu"
```

### When dependencies change

```bash
ssh user@server "cd /opt/assistant-mithu && venv/bin/pip install -r requirements.txt && systemctl restart assistant-mithu"
```

---

## Alternatives Considered and Rejected

| Category | Rejected | Why Not |
|----------|----------|---------|
| **Message queue** | Redis, RabbitMQ | Zero justification at this scale. Two bots, one message at a time per user. SQLite + asyncio handles all coordination needed. Redis adds a service to operate, a failure mode, and RAM cost. |
| **Web framework** | FastAPI | No HTTP API surface needed. Telegram is the only interface. FastAPI would be correct for Goal 2 Option B (web dashboard) but that is explicitly a later phase. |
| **Database** | PostgreSQL, MySQL | Two isolated personal assistants with low write volume. SQLite is the right choice. PostgreSQL would require running a separate service and adds operational complexity for no benefit. |
| **Token counting** | LangChain tokenizer utilities | LangChain is a large dependency with frequent breaking changes. Use `tiktoken` directly (or the simple chars-to-tokens heuristic at ~4 chars/token) for context budget management. |
| **Subprocess wrapper** | `anyio`, `trio` | The bot is already asyncio-native (PTB uses asyncio). Mixing runtimes via anyio adds complexity. `asyncio.create_subprocess_exec` is sufficient. |
| **ORM** | SQLAlchemy | Adds complexity for a schema that's already defined in `models.py` as raw SQL. The `aiosqlite` wrapper with direct SQL is simpler and more transparent for this use case. |
| **Async HTTP** | `aiohttp` (replacing httpx) | httpx already works correctly. `aiohttp` is marginally faster at high concurrency but this project makes ~1-2 Ollama requests per message. Not worth a migration. |
| **Long-lived subprocess per topic** | Persistent `claude` process per topic | While the Claude Agent SDK supports this pattern, it creates complex pipe management, potential stalls, and difficult teardown logic in a bot context. The stateless `-p --resume` pattern achieves the same session continuity with much simpler code. |
| **`--bare` mode for Claude CLI** | `claude --bare -p` | Bare mode skips OAuth and project config. For Goal 2, the OAuth session (Claude Pro/Max) and project-specific `.claude/` settings must persist. Bare mode is only for CI where you provide an API key explicitly. |

---

## Stack Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Ollama OOM on 8GB VPS | Medium | Set `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`. Monitor with `journalctl -u ollama`. |
| Claude CLI process hangs | Medium | Wrap all `communicate()` calls in `asyncio.wait_for()` with a 300s ceiling. Kill + reap on timeout. |
| SQLite write contention within a single bot | Low | Single-writer async model via aiosqlite thread queue. WAL enabled. Not a realistic risk for personal-use volume. |
| `Restart=on-failure` loop for bad config | Low | Fix: always test `python -m app.main` manually before enabling the systemd service. If the service crashes immediately, `systemctl status` and `journalctl` show the reason. |
| Token budget overrun for Qwen3:4b (8k context) | High | Context budget management is the core of the personality layer design. Must be implemented before deployment. The `tiktoken` approximation approach is acceptable; track `num_tokens` per assembled prompt and truncate/summarize conversation history before it exceeds budget. |
| Claude CLI version drift | Low | The `claude` binary is managed by the user's Claude Pro/Max subscription auto-update. Pin nothing; accept that the CLI API may evolve. Use `--output-format json` (stable interface) rather than parsing raw text output. |
| rsync overwrites live data accidentally | Low | The `--exclude 'data/'` rule in `deploy.sh` prevents this. Validate with `rsync --dry-run` before live runs. |

---

## Installation

### VPS initial setup

```bash
# Python environment (Ubuntu 24.04 ships Python 3.12)
sudo apt install -y python3-venv python3-pip

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:4b

# Bot user
sudo useradd -r -s /bin/false assistant
sudo mkdir -p /opt/assistant-mithu /opt/assistant-friend
sudo chown assistant:assistant /opt/assistant-mithu /opt/assistant-friend
```

### Per-bot venv

```bash
cd /opt/assistant-mithu
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```

### requirements.txt (final)

```
python-telegram-bot[job-queue]==21.3
python-dotenv==1.0.1
httpx==0.27.0
aiosqlite==0.20.0
tiktoken>=0.7.0
```

`tiktoken` is the only addition to the existing `requirements.txt`. It is needed for the context budget management layer.

---

## Sources

- Ollama FAQ on `OLLAMA_NUM_PARALLEL` and queue behavior: https://docs.ollama.com/faq
- Ollama parallel request behavior details: https://www.glukhov.org/post/2025/05/how-ollama-handles-parallel-requests/
- Ollama GitHub issue on concurrent requests: https://github.com/ollama/ollama/issues/9054
- Claude CLI headless/print mode official docs: https://code.claude.com/docs/en/headless
- Claude CLI `--resume` and session IDs: https://code.claude.com/docs/en/headless#continue-conversations
- Python asyncio subprocess docs: https://docs.python.org/3/library/asyncio-subprocess.html
- Claude CLI large stdin issue: https://github.com/anthropics/claude-code/issues/7263
- aiosqlite PyPI: https://pypi.org/project/aiosqlite/
- SQLite WAL mode: https://sqlite.org/wal.html
- SQLite isolation: https://sqlite.org/isolation.html
- systemd resource control: https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html
- httpx vs aiohttp comparison: https://oxylabs.io/blog/httpx-vs-requests-vs-aiohttp
- python-telegram-bot JobQueue / APScheduler: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions---JobQueue
- Qwen3-4B memory requirements: https://apxml.com/models/qwen3-4b
