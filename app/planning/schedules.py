from app.storage.db import execute, fetchall
from app.utils.time import today_str


async def create_reminder(
    title: str,
    remind_at: str,
    message: str = "",
    task_id: int | None = None,
) -> int:
    return await execute(
        "INSERT INTO reminders (title, message, remind_at, task_id) VALUES (?, ?, ?, ?)",
        (title, message, remind_at, task_id),
    )


async def list_pending_reminders() -> list[dict]:
    return await fetchall(
        "SELECT * FROM reminders WHERE status = 'pending' ORDER BY remind_at ASC"
    )


async def get_due_reminders(current_time: str) -> list[dict]:
    return await fetchall(
        "SELECT * FROM reminders WHERE status = 'pending' AND remind_at <= ?",
        (current_time,),
    )


async def mark_reminder_sent(reminder_id: int):
    await execute(
        "UPDATE reminders SET status = 'sent', sent_at = datetime('now') WHERE id = ?",
        (reminder_id,),
    )
