import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app.config import TELEGRAM_TOKEN, TELEGRAM_USER_ID
from app.bot.commands import start_command, help_command, me_command
from app.bot.handlers import message_handler
from app.bot.jobs import setup_jobs
from app.storage.migrations import run_migrations
from app.memory.vault import ensure_vault_structure
from app.utils.logging import setup_logging
from app.llm.conversation_state import load_conversation_state

logger = logging.getLogger(__name__)


async def post_init(application: Application):
    await run_migrations()
    await ensure_vault_structure()
    state = await load_conversation_state(TELEGRAM_USER_ID)
    # Store signal for first-message handler (CTX-03)
    application.bot_data["continuity_signal"] = state["signal"]
    application.bot_data["continuity_summary"] = state.get("summary_text")
    logger.info(f"Continuity signal: {state['signal']}")
    logger.info("Assistant ready.")


def main():
    setup_logging()

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    user_filter = filters.User(user_id=TELEGRAM_USER_ID)

    # Minimal commands — the bot is primarily natural language
    app.add_handler(CommandHandler("start", start_command, filters=user_filter))
    app.add_handler(CommandHandler("help",  help_command,  filters=user_filter))
    app.add_handler(CommandHandler("me",    me_command,    filters=user_filter))

    # All other interaction handled through natural language
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & user_filter, message_handler, block=False)
    )

    if app.job_queue is not None:
        setup_jobs(app.job_queue, TELEGRAM_USER_ID)
    else:
        logger.warning("JobQueue not available — install python-telegram-bot[job-queue] to enable scheduled jobs")

    logger.info(f"Starting bot for user_id={TELEGRAM_USER_ID}")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
