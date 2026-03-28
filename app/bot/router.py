import logging
import re
from app.llm.classifier import classify
from app.llm.ollama_client import generate
from app.llm.response_builder import build_answer, build_retrieval_answer, build_compare_answer
from app.llm.prompts import (
    TASK_EXTRACT_PROMPT,
    REMINDER_EXTRACT_PROMPT,
    DECISION_EXTRACT_PROMPT,
    COMPLETE_TASK_EXTRACT_PROMPT,
    PREFERENCE_EXTRACT_PROMPT,
)
from app.llm.prompt_builder import build_system_prompt
from app.planning.tasks import create_task, list_tasks, complete_task
from app.planning.routines import create_routine, list_routines
from app.planning.schedules import create_reminder, list_pending_reminders
from app.planning.reviews import generate_daily_summary, generate_eod_review
from app.memory.vault import write_inbox, search_vault, write_decision
from app.memory.comparison import compare_against_prior
from app.storage.db import execute, fetchall
from app.utils.time import today_str, now, format_dt
from app.utils.text import fmt_task_line, fmt_reminder_line

logger = logging.getLogger(__name__)

CAPABILITY_REFUSALS = {
    "code": [
        r"\bwrite (a |an |some )?(function|script|program|class|code|snippet)\b",
        r"\bdebug (this|my|the)\b",
        r"\bexplain (this |the )?(code|function|algorithm|recursion|loop)\b",
        r"\bhow (does|do) .{0,40} (code|algorithm|function|script|program) work\b",
        r"\bfix (this|my|the) (code|bug|error|script)\b",
        r"\brefactor\b",
        r"\b(python|javascript|typescript|sql|bash|html|css|rust|go|java|c\+\+)\b",
    ],
    "math": [
        r"\b(solve|calculate|compute|evaluate|find the value of)\b",
        r"\b(equation|integral|derivative|matrix|factorial)\b",
        r"\bwhat is \d+\s*[\+\-\*\/\^]\s*\d+\b",
        r"\bcompound interest\b",
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


def _parse_kv(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip().lower()] = value.strip()
    return result


async def route(message: str) -> str:
    intent = await classify(message)
    logger.info(f"Intent: {intent} | message: {message[:60]!r}")

    # ── Capture note ──────────────────────────────────────────────────────────
    if intent == "capture_note":
        ts = format_dt(now())
        write_inbox(message, ts)
        return "📥 Saved to inbox."

    # ── Create task ───────────────────────────────────────────────────────────
    if intent == "create_task":
        raw = await generate(TASK_EXTRACT_PROMPT.format(message=message))
        ex = _parse_kv(raw)
        title = ex.get("title") or message[:80]
        due = ex.get("due") or ""
        priority = {"high": 2, "normal": 1, "low": 0}.get(
            (ex.get("priority") or "normal").lower(), 1
        )
        task_id = await create_task(title=title, due_date=due, priority=priority)
        reply = f"✅ Task added: *{title}*"
        if due:
            reply += f" — due {due}"
        return reply

    # ── Set reminder ──────────────────────────────────────────────────────────
    if intent == "set_reminder":
        raw = await generate(REMINDER_EXTRACT_PROMPT.format(message=message, today=today_str()))
        ex = _parse_kv(raw)
        title = ex.get("title") or message[:80]
        when = ex.get("when") or ""
        note = ex.get("note") or ""
        if not when:
            return (
                "I understood you want a reminder, but couldn't pin down the exact time. "
                "Can you tell me the date and time? e.g. 'remind me Friday at 5pm to review the pitch'"
            )
        reminder_id = await create_reminder(title=title, remind_at=when, message=note)
        return f"⏰ Reminder set: *{title}* at {when}"

    # ── List tasks ────────────────────────────────────────────────────────────
    if intent == "list_tasks":
        due_today = any(w in message.lower() for w in ["today", "due", "this week"])
        tasks = await list_tasks(due_today=due_today)
        if not tasks:
            return "No open tasks." if not due_today else "Nothing due today."
        lines = "\n".join(fmt_task_line(t) for t in tasks)
        header = "Due today:" if due_today else "Open tasks:"
        return f"*{header}*\n{lines}"

    # ── Complete task ─────────────────────────────────────────────────────────
    if intent == "complete_task":
        tasks = await list_tasks()
        if not tasks:
            return "No open tasks to mark complete."
        task_list = "\n".join(f"{t['id']}: {t['title']}" for t in tasks)
        raw = await generate(
            COMPLETE_TASK_EXTRACT_PROMPT.format(message=message, task_list=task_list)
        )
        try:
            task_id = int(raw.strip())
        except ValueError:
            task_id = 0
        if not task_id:
            return "I'm not sure which task you mean. Can you be more specific?"
        ok = await complete_task(task_id)
        if ok:
            match = next((t for t in tasks if t["id"] == task_id), None)
            name = match["title"] if match else f"task {task_id}"
            return f"✅ Done: *{name}*"
        return f"Couldn't find that task."

    # ── Set reminder — list ───────────────────────────────────────────────────
    if intent == "list_reminders":
        reminders = await list_pending_reminders()
        if not reminders:
            return "No pending reminders."
        lines = "\n".join(fmt_reminder_line(r) for r in reminders)
        return f"*Pending reminders:*\n{lines}"

    # ── Create routine ────────────────────────────────────────────────────────
    if intent == "create_routine":
        raw = await generate(
            f"Extract a routine from this message.\n\nMessage: {message}\n\n"
            "Respond in this format:\nName: <routine name>\nSchedule type: <daily/weekly/monthly>\n"
            "Schedule value: <time or day+time, e.g. 09:00 or Monday 09:00>\nDescription: <brief description>"
        )
        ex = _parse_kv(raw)
        name = ex.get("name") or message[:60]
        schedule_type = ex.get("schedule type") or "daily"
        schedule_value = ex.get("schedule value") or "09:00"
        description = ex.get("description") or ""
        routine_id = await create_routine(name, description, schedule_type, schedule_value)
        return f"🔁 Routine created: *{name}* ({schedule_type}, {schedule_value})"

    # ── Update preference ─────────────────────────────────────────────────────
    if intent == "update_preference":
        raw = await generate(PREFERENCE_EXTRACT_PROMPT.format(message=message))
        ex = _parse_kv(raw)
        key = ex.get("key") or ""
        value = ex.get("value") or ""
        source = ex.get("source") or message[:200]
        if key and value:
            await execute(
                """INSERT INTO preferences (key, value, source) VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                   source=excluded.source, updated_at=datetime('now')""",
                (key, value, source),
            )
            echo = f"Saved: I'll {source.lower().rstrip('.')}."
            return echo
        return "Got it — I noted your preference."

    # ── Search ────────────────────────────────────────────────────────────────
    if intent == "search":
        query = message.lower().replace("search", "").replace("find", "").replace("look for", "").strip()
        if not query:
            query = message
        parts = []
        tasks = await list_tasks()
        matched = [t for t in tasks if query in t["title"].lower()]
        if matched:
            parts.append("*Tasks:*\n" + "\n".join(fmt_task_line(t) for t in matched[:5]))
        decisions = await fetchall(
            "SELECT title, decision_date FROM decision_index WHERE title LIKE ? OR summary LIKE ? LIMIT 5",
            (f"%{query}%", f"%{query}%"),
        )
        if decisions:
            parts.append("*Decisions:*\n" + "\n".join(f"- {d['decision_date']}: {d['title']}" for d in decisions))
        vault_hits = search_vault(query, max_results=5)
        if vault_hits:
            parts.append("*Notes:*\n" + "\n".join(f"- `{h['path']}`: {h['snippet']}" for h in vault_hits))
        return "\n\n".join(parts) if parts else f"Nothing found for: {query}"

    # ── Project update ────────────────────────────────────────────────────────
    if intent == "project_update":
        ts = format_dt(now())
        write_inbox(f"[project update] {message}", ts)
        return "📥 Project update noted and saved to inbox for review."

    # ── Retrieval ─────────────────────────────────────────────────────────────
    if intent == "retrieval_query":
        return await build_retrieval_answer(message)

    # ── Compare ───────────────────────────────────────────────────────────────
    if intent == "compare_context":
        return await build_compare_answer(message)

    # ── Daily summary ─────────────────────────────────────────────────────────
    if intent == "daily_summary":
        return await generate_daily_summary()

    # ── End of day ────────────────────────────────────────────────────────────
    if intent == "end_of_day_review":
        return await generate_eod_review()

    # ── Draft ─────────────────────────────────────────────────────────────────
    if intent == "draft_reply":
        system = await build_system_prompt()
        draft = await generate(
            f"Draft the following. Return only the draft text, no preamble:\n\n{message}",
            system=system,
        )
        return f"*Draft:*\n\n{draft}\n\n_Reply 'send it' or 'post this' to confirm, or ignore to discard._"

    # ── Capability refusal (general_answer only) ──────────────────────────────
    if intent == "answer":
        refusal = _capability_refusal_check(message)
        if refusal:
            logger.info(f"Capability refusal fired | message: {message[:60]!r}")
            return refusal

    # ── Default: answer ───────────────────────────────────────────────────────
    return await build_answer(message)
