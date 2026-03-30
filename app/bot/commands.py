import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.planning.tasks import create_task, list_tasks, complete_task
from app.planning.routines import create_routine, list_routines
from app.planning.schedules import create_reminder, list_pending_reminders
from app.planning.reviews import generate_daily_summary, generate_eod_review
from app.memory.vault import write_inbox, search_vault, write_decision
from app.storage.db import execute, fetchall, fetchone
from app.llm.ollama_client import generate, check_ollama
from app.llm.prompts import (
    TASK_EXTRACT_PROMPT,
    REMINDER_EXTRACT_PROMPT,
    DECISION_EXTRACT_PROMPT,
    SYSTEM_PROMPT,
)
from app.config import ASSISTANT_NAME
from app.utils.time import today_str, now, format_dt
from app.utils.text import fmt_task_line, fmt_reminder_line, fmt_routine_line

logger = logging.getLogger(__name__)

HELP_TEXT = """\
*Tintu — Planning Assistant*

Just talk to me in plain language. Examples:

*Tasks*
"Add a task to review the pitch deck"
"What's on my list?"
"I finished the client call"

*Reminders*
"Remind me Friday at 5pm to send the invoice"
"Ping me tomorrow morning about the meeting"

*Notes & decisions*
"Save this: we decided to go with Qwen for the model"
"Log a decision — we're dropping the Discord integration for now"

*Retrieval*
"What did we decide about the model?"
"What tasks are due this week?"
"Find my notes on the assistant project"

*Summaries*
"Give me a daily summary"
"End of day review"

*Preferences*
"I prefer morning summaries at 8am"
"Always tag fitness tasks under the health project"
"""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ollama_ok = await check_ollama()
    status = "Language model online." if ollama_ok else "Language model offline — Ollama not reachable."
    await update.message.reply_text(
        f"*Hi, I'm {ASSISTANT_NAME}.*\n\n"
        f"I'm your private planning and memory assistant. Here's what I can do:\n\n"
        f"*What I'm good at:*\n"
        f"- Tasks, reminders, and routines\n"
        f"- Capturing notes, decisions, and project updates\n"
        f"- Summarizing your day or week\n"
        f"- Finding things you've told me before\n\n"
        f"*What I can't do:*\n"
        f"- Code, math, or research\n"
        f"- Anything requiring real-time or external information\n"
        f"- Complex analysis or editing\n\n"
        f"*How to use me:*\n"
        f"Just talk to me in plain language — no commands needed for most things. "
        f"Try telling me a task, asking what's on your list, or saying something like "
        f"\"remind me Friday at 5pm to review the contract\".\n\n"
        f"You can also shape how I work: tell me to be more direct, use a different tone, "
        f"or focus on a specific project — I'll remember.\n\n"
        f"_Status: {status}_\n\n"
        f"Send /help to see all commands, or just start talking.",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: `/inbox <your note>`", parse_mode="Markdown")
        return
    ts = format_dt(now())
    path = write_inbox(text, ts)
    await update.message.reply_text(f"📥 Saved to inbox.\n`{path.name}`", parse_mode="Markdown")


async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Usage:\n`/task add <title>`\n`/task list`\n`/task today`\n`/task done <id>`",
            parse_mode="Markdown",
        )
        return

    sub = args[0].lower()

    if sub == "add":
        title = " ".join(args[1:])
        if not title:
            await update.message.reply_text("Provide a task title.")
            return
        # Use LLM to extract due date / priority if present
        raw = await generate(TASK_EXTRACT_PROMPT.format(message=title))
        extracted = _parse_key_value(raw)
        task_id = await create_task(
            title=extracted.get("title") or title,
            due_date=extracted.get("due") or "",
            priority={"high": 2, "normal": 1, "low": 0}.get(
                (extracted.get("priority") or "normal").lower(), 1
            ),
        )
        reply = f"✅ Task `{task_id}` created: *{extracted.get('title') or title}*"
        if extracted.get("due"):
            reply += f"\nDue: {extracted['due']}"
        await update.message.reply_text(reply, parse_mode="Markdown")

    elif sub == "list":
        tasks = await list_tasks()
        if not tasks:
            await update.message.reply_text("No open tasks.")
            return
        lines = "\n".join(fmt_task_line(t) for t in tasks)
        await update.message.reply_text(f"*Open tasks:*\n{lines}", parse_mode="Markdown")

    elif sub == "today":
        tasks = await list_tasks(due_today=True)
        if not tasks:
            await update.message.reply_text("No tasks due today.")
            return
        lines = "\n".join(fmt_task_line(t) for t in tasks)
        await update.message.reply_text(f"*Due today:*\n{lines}", parse_mode="Markdown")

    elif sub == "done":
        if len(args) < 2 or not args[1].isdigit():
            await update.message.reply_text("Usage: `/task done <id>`", parse_mode="Markdown")
            return
        task_id = int(args[1])
        ok = await complete_task(task_id)
        if ok:
            await update.message.reply_text(f"✅ Task `{task_id}` marked done.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"Task `{task_id}` not found.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Unknown subcommand. Use: add, list, today, done")


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text(
            "Usage: `/remind <natural language>`\nExample: `/remind Friday 5pm review pitch`",
            parse_mode="Markdown",
        )
        return

    raw = await generate(REMINDER_EXTRACT_PROMPT.format(message=text, today=today_str()))
    extracted = _parse_key_value(raw)

    title = extracted.get("title") or text
    when = extracted.get("when") or ""
    note = extracted.get("note") or ""

    if not when:
        await update.message.reply_text(
            "Could not extract a date/time. Try: `/remind 2026-03-27 17:00 review pitch`",
            parse_mode="Markdown",
        )
        return

    reminder_id = await create_reminder(title=title, remind_at=when, message=note)
    await update.message.reply_text(
        f"⏰ Reminder `{reminder_id}` set:\n*{title}*\nAt: {when}",
        parse_mode="Markdown",
    )


async def routine_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Usage:\n`/routine add <name> | <schedule>`\n`/routine list`",
            parse_mode="Markdown",
        )
        return

    sub = args[0].lower()

    if sub == "add":
        rest = " ".join(args[1:])
        if "|" not in rest:
            await update.message.reply_text(
                "Format: `/routine add <name> | <schedule>`\nExample: `/routine add Morning review | daily 09:00`",
                parse_mode="Markdown",
            )
            return
        name, schedule = [p.strip() for p in rest.split("|", 1)]
        parts = schedule.split(None, 1)
        schedule_type = parts[0] if parts else "daily"
        schedule_value = parts[1] if len(parts) > 1 else schedule
        routine_id = await create_routine(name, "", schedule_type, schedule_value)
        await update.message.reply_text(
            f"🔁 Routine `{routine_id}` created: *{name}*\nSchedule: {schedule}",
            parse_mode="Markdown",
        )

    elif sub == "list":
        routines = await list_routines()
        if not routines:
            await update.message.reply_text("No active routines.")
            return
        lines = "\n".join(fmt_routine_line(r) for r in routines)
        await update.message.reply_text(f"*Routines:*\n{lines}", parse_mode="Markdown")
    else:
        await update.message.reply_text("Unknown subcommand. Use: add, list")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: `/search <query>`", parse_mode="Markdown")
        return

    results = []

    # Tasks
    tasks = await list_tasks()
    matched_tasks = [t for t in tasks if query.lower() in t["title"].lower()]
    if matched_tasks:
        lines = "\n".join(fmt_task_line(t) for t in matched_tasks[:5])
        results.append(f"*Tasks:*\n{lines}")

    # Decisions
    decisions = await fetchall(
        "SELECT title, decision_date FROM decision_index WHERE title LIKE ? OR summary LIKE ? LIMIT 5",
        (f"%{query}%", f"%{query}%"),
    )
    if decisions:
        lines = "\n".join(f"- {d['decision_date']}: {d['title']}" for d in decisions)
        results.append(f"*Decisions:*\n{lines}")

    # Vault
    vault_hits = search_vault(query, max_results=5)
    if vault_hits:
        lines = "\n".join(f"- `{h['path']}`: {h['snippet']}" for h in vault_hits)
        results.append(f"*Notes:*\n{lines}")

    if results:
        await update.message.reply_text("\n\n".join(results), parse_mode="Markdown")
    else:
        await update.message.reply_text(f"No results found for: *{query}*", parse_mode="Markdown")


async def decision_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text(
            "Usage: `/decision <describe your decision>`",
            parse_mode="Markdown",
        )
        return

    raw = await generate(DECISION_EXTRACT_PROMPT.format(message=text))
    extracted = _parse_key_value(raw)

    title = extracted.get("title") or text[:60]
    date_str = today_str()

    content = f"""# {title}

**Date:** {date_str}
**Context:** {extracted.get('context', '')}
**Decision:** {extracted.get('decision', text)}
**Reason:** {extracted.get('reason', '')}
**Alternatives:** {extracted.get('alternatives', 'none')}
**Implications:** {extracted.get('implications', 'none')}
"""
    path = write_decision(date_str, title, content)
    decision_id = await execute(
        "INSERT INTO decision_index (title, decision_date, markdown_path, summary) VALUES (?, ?, ?, ?)",
        (title, date_str, str(path), extracted.get("decision", text[:200])),
    )
    await update.message.reply_text(
        f"📋 Decision `{decision_id}` logged: *{title}*\n`vault/decisions/{path.name}`",
        parse_mode="Markdown",
    )


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Generating daily summary…")
    summary = await generate_daily_summary()
    await update.message.reply_text(summary)


async def eod_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Generating end-of-day review…")
    review = await generate_eod_review()
    await update.message.reply_text(review)


async def project_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    sub = args[0].lower() if args else "list"

    if sub == "list":
        projects = await fetchall("SELECT id, name, status, phase FROM projects ORDER BY id")
        if not projects:
            await update.message.reply_text("No projects yet.")
            return
        lines = "\n".join(
            f"- `{p['id']}` *{p['name']}* [{p['status']}]" + (f" — {p['phase']}" if p.get("phase") else "")
            for p in projects
        )
        await update.message.reply_text(f"*Projects:*\n{lines}", parse_mode="Markdown")

    elif sub == "summary":
        name = " ".join(args[1:])
        if not name:
            await update.message.reply_text("Usage: `/project summary <name>`", parse_mode="Markdown")
            return
        project = await fetchone(
            "SELECT * FROM projects WHERE name LIKE ? OR slug LIKE ?",
            (f"%{name}%", f"%{name}%"),
        )
        if not project:
            await update.message.reply_text(f"Project not found: *{name}*", parse_mode="Markdown")
            return
        tasks = await list_tasks(project_id=project["id"])
        task_lines = "\n".join(fmt_task_line(t) for t in tasks) or "none"
        summary_prompt = (
            f"Summarize the project '{project['name']}'.\n"
            f"Status: {project['status']}\n"
            f"Phase: {project.get('phase') or 'unknown'}\n"
            f"Summary on file: {project.get('summary') or 'none'}\n"
            f"Open tasks:\n{task_lines}"
        )
        summary = await generate(summary_prompt, system=SYSTEM_PROMPT)
        await update.message.reply_text(summary)
    else:
        await update.message.reply_text("Usage: `/project list` or `/project summary <name>`", parse_mode="Markdown")


async def draft_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: `/draft <what to draft>`", parse_mode="Markdown")
        return
    draft = await generate(
        f"Draft the following. Do not send. Return only the draft text:\n\n{text}",
        system=SYSTEM_PROMPT,
    )
    context.user_data["last_draft"] = draft
    await update.message.reply_text(
        f"*Draft ready:*\n\n{draft}\n\n_Reply /post to send, or discard._",
        parse_mode="Markdown",
    )


async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get("last_draft")
    if not draft:
        await update.message.reply_text("No draft to post. Use /draft first.")
        return
    # Two-step: show draft and ask for confirmation
    context.user_data["pending_post"] = draft
    context.user_data.pop("last_draft", None)
    await update.message.reply_text(
        f"*Ready to post:*\n\n{draft}\n\nReply *yes* to confirm, anything else cancels.",
        parse_mode="Markdown",
    )


async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sections = [f"*What {ASSISTANT_NAME} knows about you*\n"]

    # Open tasks
    tasks = await list_tasks()
    if tasks:
        lines = "\n".join(fmt_task_line(t) for t in tasks[:10])
        sections.append(f"*Open tasks ({len(tasks)}):*\n{lines}")
    else:
        sections.append("*Open tasks:* none")

    # Pending reminders
    reminders = await list_pending_reminders()
    if reminders:
        lines = "\n".join(fmt_reminder_line(r) for r in reminders[:5])
        sections.append(f"*Pending reminders ({len(reminders)}):*\n{lines}")
    else:
        sections.append("*Pending reminders:* none")

    # Personality traits
    traits = await fetchall("SELECT key, value FROM personality_traits ORDER BY key")
    if traits:
        lines = "\n".join(f"- {r['key']}: {r['value']}" for r in traits)
        sections.append(f"*Personality traits:*\n{lines}")
    else:
        sections.append("*Personality traits:* none captured yet")

    # Behavioral preferences
    prefs = await fetchall("SELECT key, value FROM preferences ORDER BY key")
    if prefs:
        lines = "\n".join(f"- {r['key']}: {r['value']}" for r in prefs)
        sections.append(f"*Preferences:*\n{lines}")
    else:
        sections.append("*Preferences:* none captured yet")

    # Vault stats
    from app.config import VAULT_PATH
    note_count = sum(1 for _ in VAULT_PATH.rglob("*.md")) if VAULT_PATH.exists() else 0
    sections.append(f"*Vault:* {note_count} notes")

    # Last session summary
    last_summary = await fetchone(
        "SELECT summary_text, created_at FROM session_summaries ORDER BY created_at DESC LIMIT 1"
    )
    if last_summary:
        sections.append(
            f"*Last session summary ({last_summary['created_at'][:10]}):*\n{last_summary['summary_text'][:400]}"
        )
    else:
        sections.append("*Last session summary:* none yet")

    await update.message.reply_text("\n\n".join(sections), parse_mode="Markdown")


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_key_value(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip().lower()] = value.strip()
    return result
