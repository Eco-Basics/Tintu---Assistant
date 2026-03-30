import logging
from telegram.ext import JobQueue
from app.planning.schedules import get_due_reminders, mark_reminder_sent
from app.utils.time import now

logger = logging.getLogger(__name__)


def setup_jobs(job_queue: JobQueue, user_id: int):
    job_queue.run_repeating(
        check_reminders,
        interval=60,
        first=10,
        data=user_id,
        name="reminder_checker",
    )
    logger.info("Jobs scheduled.")


async def check_reminders(context):
    user_id = context.job.data
    current_time = now().strftime("%Y-%m-%d %H:%M")

    due = await get_due_reminders(current_time)
    for reminder in due:
        text = f"⏰ *Reminder:* {reminder['title']}"
        if reminder.get("message"):
            text += f"\n{reminder['message']}"
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="Markdown",
            )
            await mark_reminder_sent(reminder["id"])
            logger.info(f"Sent reminder id={reminder['id']}")
        except Exception as e:
            logger.error(f"Failed to send reminder {reminder['id']}: {e}")
