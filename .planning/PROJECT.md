# Tintu — Personal AI Assistant Platform

## What This Is

Two independent AI assistants running on Qwen3:4b (Ollama) on a shared Hetzner CX33 VPS, each serving a different person via Telegram. Personalities are not hardcoded — they evolve through natural conversation as users shape behavior and preferences over time. A second goal adds multi-session Claude Code access via Telegram group topics, enabling parallel project work without a browser.

## Core Value

Each user gets an assistant that genuinely adapts to them — remembering how they like to work, speaking in a style they've shaped, and staying within its honest capabilities.

## Requirements

### Validated

- ✓ Telegram bot receives natural language messages — existing
- ✓ Intent classification (keyword-first + LLM fallback) — existing
- ✓ SQLite database with tasks, reminders, routines, decisions, preferences, logs — existing
- ✓ Obsidian-compatible Markdown vault (inbox, daily, projects, decisions, etc.) — existing
- ✓ Ollama client for Qwen3:4b local inference — existing
- ✓ Full intent router: capture note, create task, set reminder, complete task, list tasks, create routine, update preference, search, retrieval, comparison, daily summary, EOD review, draft — existing
- ✓ Scheduled reminder delivery (60s check interval) — existing
- ✓ Two separate deployments (assistant-mithu, assistant-friend) with isolated DBs and vaults — existing
- ✓ systemd service files for both bots — existing
- ✓ Backup script — existing

### Active

**Goal 1 — Adaptive personality layer:**
- [ ] Dynamic system prompt assembly from personality traits + behavior preferences tables
- [ ] Personality signals detected from natural conversation and persisted (e.g. "be more direct", "act like a coach")
- [ ] Behavior preferences persisted (e.g. "skip confirmation before creating tasks")
- [ ] Named personas definable on the fly (e.g. "act like a brutally honest advisor")
- [ ] Context budget manager: enforces per-slot token limits across system prompt, active tasks, retrieved memory, conversation history
- [ ] Rolling conversation compression: oldest turns summarized after budget exceeded
- [ ] Session summarization: after ~20 turns, session compressed and stored; next session starts fresh with summary available in retrieval
- [ ] Active tasks injected capped at 5 (most urgent/recent only)
- [ ] Retrieved memory is relevance-filtered, not full dump
- [ ] Qwen explicit capability refusal: declines code, math, research, external info with clear message

**Goal 2 — Multi-session Claude via Telegram:**
- [ ] Telegram group with Forum/Topics mode set up
- [ ] Bot routes each topic's messages to a corresponding Claude Code process on VPS
- [ ] Each project has its own directory with persistent Claude Code session history
- [ ] New project can be added by creating a new topic + directory (no new bot token required)
- [ ] Sessions are independent — activity in one topic doesn't affect others

### Out of Scope

- Fallback to a more capable model for tasks Qwen refuses — clean refusal is the design; no API access
- Mode system / model routing — over-engineered for current needs
- Real-time web search for Qwen assistant — no external API
- Option B web dashboard (FastAPI + WebSocket) — planned for after Option A is proven
- Multi-user support per bot — each bot serves exactly one Telegram user ID
- Mobile app or web UI for Goal 1 assistant — Telegram only

## Context

- **Existing codebase:** Phase 1 + 2 fully implemented at `C:\Tintu, the Assistant\`. Code is complete and ready to deploy — blocked only on Hetzner VPS provisioning.
- **Model choice:** Qwen3:4b via Ollama. Adequate for assistant core tasks. Ceiling is complex reasoning and code. Personality adaptation is a system-level concern, not model-level.
- **Two users:** Mithu (user ID `7912940724`, timezone Asia/Kolkata) and a friend (token + ID + timezone TBD).
- **Goal 2 constraint:** No Anthropic API. Claude Code CLI uses claude.ai OAuth (Pro/Max subscription). Multi-session requires running N independent `claude` processes, one per project directory.
- **Deployment target:** Hetzner CX33 (4 vCPU, 8GB RAM, Ubuntu 24.04). Both bots + Ollama share one server.

## Constraints

- **Model:** Qwen3:4b only — no API key, no external model calls for Goal 1
- **Context window:** ~8k tokens hard limit for Qwen3:4b — context budget manager is mandatory, not optional
- **VPS:** CX33 — must share RAM between 2 bot processes + Ollama; no memory-heavy background jobs
- **Claude sessions (Goal 2):** Bound to Pro/Max subscription via CLI OAuth — not an API, cannot be scripted arbitrarily; must use `claude` CLI subprocess
- **Telegram:** Goal 2 requires a group with Forum/Topics mode enabled (not a DM bot)

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Qwen3:4b as sole model | No API access; local inference only; 4b adequate for assistant tasks | — Pending |
| No fallback model | Clean refusal > confident wrong answer; complexity not justified | — Pending |
| Dynamic system prompt from DB | Personality must survive context resets and persist across sessions | — Pending |
| Context budget manager (hard limits) | 8k window; overloading degrades task quality more than restricting context | — Pending |
| Session summarization after ~20 turns | Prevents context bloat; summary available via retrieval not pre-loaded | — Pending |
| TG group + topics for Goal 2 (Option A) | Simplest viable path to parallel sessions; no new bot tokens per project | — Pending |
| Option B (web dashboard) deferred | Option A validates the need first; dashboard is upgrade path, not starting point | — Pending |

---
*Last updated: 2026-03-27 after project initialization*
