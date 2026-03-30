# Tintu — Project Goals & Decisions

*Last updated: 2026-03-30*

---

## Goal 1: Two adaptive personal assistants on Qwen3:1.7b

### What we're building

Two fully independent assistant deployments on a shared Hetzner CX33 VPS. Each serves a different person with a distinct, evolving personality — not hardcoded, but shaped over time through natural conversation.

### Users

- **Mithu** — user ID `7912940724`, assistant named **Dene**
- **Friend** — separate bot, separate DB, separate vault, separate personality profile, assistant named **Ingle**

### Adaptive personality architecture

The model itself does not learn. The system around it does. Each conversation, the system prompt is assembled dynamically from layers:

```
[Base role & capabilities]          ← static, defines what the assistant is
[Personality traits]                ← accumulated from explicit user shaping
[Behavioral preferences]            ← learned from corrections and confirmations
[Active context]                    ← current tasks, recent decisions, open items
[Retrieved memory]                  ← relevant vault entries for this query
[Recent conversation]               ← last N turns, budget-controlled
```

Users shape behavior through natural language:
- "Be more direct" → updates `personality_traits` table
- "Stop confirming before creating tasks" → updates `behavior_preferences` table
- "Act like a brutally honest coach" → writes a named persona definition

This persists across conversations. The assistant's character evolves as the user uses it.

### Context window management (32k native, 8k working budget)

Both qwen3:1.7b and qwen3:4b have a **32K token native context window** (not 8K as originally assumed). We maintain a conservative 8K working budget by design — discipline here keeps response times fast and quality consistent, regardless of what the model could technically handle.

Budget allocation per request:

| Slot | Allocation | Content |
|---|---|---|
| System prompt | ~800 tokens | Role + assembled personality + behavior prefs |
| Active tasks | ~600 tokens | Open tasks due soon, pending reminders |
| Retrieved memory | ~1,500 tokens | Vault entries relevant to current query only |
| Recent conversation | ~3,500 tokens | Last 8–12 turns (trimmed if needed) |
| Response headroom | ~1,200 tokens | Room for the model to generate |
| **Total** | **~7,600 tokens** | Well within 32K; ~24K headroom available if needed |

Rules:
- **Retrieved memory is selective, not total dump.** Only inject vault entries scored relevant to the current message.
- **Conversation history is rolling.** Once recent turns exceed budget, oldest turns are summarized (1–2 sentences each) and compressed into a short "earlier in this conversation" block.
- **After ~20 turns**, the session is summarized and stored. Next conversation starts fresh with that summary available in memory retrieval, not pre-loaded.
- **Active tasks cap at 5.** Most urgent/recent only. Full list is available on request.
- **Personality + prefs are always injected** — they are the character, never dropped.

### Model decision: qwen3:1.7b

Originally planned for qwen3:4b. Switched to qwen3:1.7b after deployment testing showed:
- qwen3:4b: 2-3 minute response time on CX33 CPU (unusable)
- qwen3:1.7b: under 5 second response time (acceptable)

Quality impact is minimal for this use case — the capability refusals (math, code, research) mean 4b's stronger reasoning was never being utilized. Both models share the same 32K context window. The 1.7b also uses ~1.1GB less RAM, making dual deployment (Dene + Ingle) more comfortable on the 8GB CX33.

If response quality becomes a concern at 1.7b, the upgrade path is to a GPU-enabled server, not switching back to 4b on CPU.

### Explicit capability limits

Qwen3:1.7b is adequate for the assistant's core job. For tasks outside reliable reach, it will say so explicitly rather than hallucinate a poor answer.

System prompt will instruct Qwen to flag and decline (or warn) on:
- Multi-step mathematical computation
- Code generation or debugging
- Real-time or external information lookup
- Complex comparative research / synthesis
- Nuanced writing critique or editing

Exact phrasing in system prompt:
> If asked to do something you cannot do reliably — code, math, research, or tasks requiring external information — say clearly: "I'm not able to do this reliably. You'd be better served by a more capable model for this."

No fallback to another model. Clean refusal is better than a confident wrong answer.

### Deployment

```
/opt/
  assistant-mithu/      ← Mithu's bot, DB, vault, personality profile
  assistant-friend/     ← Friend's bot, DB, vault, personality profile
  (ollama shared as system service)
```

---

## Goal 2: Multiple parallel Claude sessions from VPS

### Problem

Current Claude Code + Telegram setup is single-threaded. One active project at a time. Need to run multiple Claude sessions concurrently, the same way you'd open multiple terminals.

### Constraint

No Anthropic API access. Pro/Max subscription only. Claude Code CLI authenticates via claude.ai OAuth — this is the entry point.

### Plan: Option A now, Option B later

---

### Option A — Telegram group with topics (implement first)

A single Telegram group with **Forum/Topics mode** enabled. Each topic maps to one project directory and one persistent Claude Code session on the VPS.

```
[TG Group: Projects]
  ├── #webapp-redesign    → /opt/projects/webapp/      (claude session A)
  ├── #api-backend        → /opt/projects/api/          (claude session B)
  └── #research           → /opt/projects/research/     (claude session C)
```

How it works:
- A bot routes each topic's messages to the corresponding Claude Code process
- Each project directory has its own `.claude/` history — sessions are persistent
- Sessions run independently; messages in topic A don't affect topic B
- New project = new topic + new directory (no new bot needed)

Limitations:
- Tasks within a single topic are still sequential (one at a time per session)
- Cross-project coordination is manual

---

### Option B — Lightweight web dashboard (plan for later)

A self-hosted web UI on the VPS. Each project gets a panel — a live terminal stream from a Claude Code subprocess, with an input field.

```
[Dashboard at vps-ip:8080]
  ┌─────────────────────┐  ┌─────────────────────┐
  │  webapp-redesign     │  │  api-backend         │
  │  > Analyzing...      │  │  > Writing tests...  │
  │  [____send_______]   │  │  [____send_______]   │
  └─────────────────────┘  └─────────────────────┘
```

Stack: FastAPI + WebSockets + minimal vanilla JS frontend. Each panel is a persistent subprocess running `claude --print` or SDK mode, piped to the WebSocket.

This is Option A's natural upgrade path — same project/session model, better interface.

---

## Open items

- [x] Hetzner CX33 provisioned (Ubuntu 24.04, Helsinki)
- [x] Dene (Mithu's bot) deployed and in production as `dene.service`
- [x] Ingle (friend's bot) deployed and in production as `ingle.service`
- [x] Self-evolving system prompt (personality_traits + preferences + personas)
- [x] `/start` onboarding, `/profile` summary, `/help` full command list
- [ ] Telegram group created with topics enabled (for Goal 2 Option A)
