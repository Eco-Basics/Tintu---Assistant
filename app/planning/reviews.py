from app.llm.ollama_client import generate
from app.llm.prompts import DAILY_SUMMARY_PROMPT, EOD_REVIEW_PROMPT
from app.storage.db import fetchall
from app.memory.vault import write_daily, read_daily
from app.utils.time import today_str


async def generate_daily_summary(date_str: str | None = None) -> str:
    date_str = date_str or today_str()

    tasks_created = await fetchall(
        "SELECT title FROM tasks WHERE date(created_at) = ? ORDER BY id",
        (date_str,),
    )
    tasks_completed = await fetchall(
        "SELECT title FROM tasks WHERE date(completed_at) = ?",
        (date_str,),
    )
    reminders = await fetchall(
        "SELECT title, remind_at FROM reminders WHERE date(created_at) = ?",
        (date_str,),
    )
    decisions = await fetchall(
        "SELECT title FROM decision_index WHERE decision_date = ?",
        (date_str,),
    )

    prompt = DAILY_SUMMARY_PROMPT.format(
        date=date_str,
        tasks_created=", ".join(t["title"] for t in tasks_created) or "none",
        tasks_completed=", ".join(t["title"] for t in tasks_completed) or "none",
        reminders=", ".join(f"{r['title']} at {r['remind_at']}" for r in reminders) or "none",
        decisions=", ".join(d["title"] for d in decisions) or "none",
    )

    summary = await generate(prompt)
    write_daily(date_str, f"# Daily Summary: {date_str}\n\n{summary}\n")
    return summary


async def generate_eod_review(date_str: str | None = None) -> str:
    date_str = date_str or today_str()

    completed = await fetchall(
        "SELECT title FROM tasks WHERE date(completed_at) = ?",
        (date_str,),
    )
    open_tasks = await fetchall(
        "SELECT title, due_date FROM tasks WHERE status NOT IN ('done','cancelled') ORDER BY due_date LIMIT 10"
    )
    decisions = await fetchall(
        "SELECT title FROM decision_index WHERE decision_date = ?",
        (date_str,),
    )
    deadlines = await fetchall(
        "SELECT title, due_date FROM tasks WHERE status NOT IN ('done','cancelled') AND due_date IS NOT NULL ORDER BY due_date LIMIT 5"
    )

    prompt = EOD_REVIEW_PROMPT.format(
        date=date_str,
        completed=", ".join(t["title"] for t in completed) or "none",
        open_tasks=", ".join(t["title"] for t in open_tasks) or "none",
        deadlines=", ".join(f"{t['title']} ({t['due_date']})" for t in deadlines) or "none",
        decisions=", ".join(d["title"] for d in decisions) or "none",
    )

    review = await generate(prompt)
    from app.memory.vault import append_daily
    append_daily(date_str, f"## End-of-Day Review\n\n{review}")
    return review
