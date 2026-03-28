import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.router import route
from app.storage.db import execute
from app.llm.conversation_state import write_conversation_turn, history_cache

logger = logging.getLogger(__name__)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.text.strip()

    # Handle pending post confirmation
    pending = context.user_data.get("pending_post")
    if pending:
        if text.lower() == "yes":
            context.user_data.pop("pending_post")
            await message.reply_text(f"Posted:\n\n{pending}")
            await execute(
                "INSERT INTO message_log (telegram_message_id, direction, kind, summary) VALUES (?, ?, ?, ?)",
                (message.message_id, "out", "post", pending[:200]),
            )
        else:
            context.user_data.pop("pending_post")
            await message.reply_text("Post cancelled.")
        return

    # Log incoming message
    await execute(
        "INSERT INTO message_log (telegram_message_id, direction, kind, summary) VALUES (?, ?, ?, ?)",
        (message.message_id, "in", "message", text[:200]),
    )

    # Route and respond
    try:
        await message.reply_chat_action("typing")
        response = await route(text)
        await message.reply_text(response, parse_mode="Markdown")
        # Phase 3: persist conversation turn and update in-memory cache
        chat_id = update.effective_chat.id
        await write_conversation_turn(chat_id, "user", text)
        await write_conversation_turn(chat_id, "assistant", response)
        history_cache.append(chat_id, "user", text)
        history_cache.append(chat_id, "assistant", response)
    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)
        await message.reply_text("Something went wrong. Please try again.")
