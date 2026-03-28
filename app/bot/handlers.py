import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.router import route
from app.storage.db import execute
from app.llm.conversation_state import write_conversation_turn, history_cache
from app.memory.summarizer import (
    get_turn_count_since_last_summary,
    generate_session_summary,
    apply_key_facts_correction,
)

logger = logging.getLogger(__name__)

SUMMARIZE_TRIGGER = 20

# Maps chat_id -> summary_id awaiting potential correction from user
_pending_corrections: dict[int, int] = {}


async def summarize_and_notify(chat_id: int, update) -> None:
    """Background task: generate session summary and send to user for review."""
    try:
        summary_text, key_facts, summary_id = await generate_session_summary(chat_id)
        if not summary_text or summary_id == 0:
            return
        msg = (
            f"*Session Summary (last {SUMMARIZE_TRIGGER} turns):*\n\n"
            f"{summary_text}"
        )
        if key_facts:
            msg += f"\n\n*Key facts captured:*\n{key_facts}"
        msg += "\n\n_If anything is wrong, reply with a correction and I'll update the record._"
        await update.get_bot().send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode="Markdown",
        )
        # Store summary_id so the next reply can be treated as a correction
        _pending_corrections[chat_id] = summary_id
        logger.info(f"Session summary sent to user chat_id={chat_id}, summary_id={summary_id}")
    except Exception as e:
        logger.error(f"summarize_and_notify failed: {e}", exc_info=True)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.text.strip()

    # Handle pending key_facts correction (from async summarization background task)
    pending_summary_id = (
        context.user_data.get("pending_summary_id")
        or _pending_corrections.get(update.effective_chat.id)
    )
    if pending_summary_id and not text.startswith("/"):
        _pending_corrections.pop(update.effective_chat.id, None)
        context.user_data.pop("pending_summary_id", None)
        corrected = await apply_key_facts_correction(pending_summary_id, text.strip())
        if corrected:
            await message.reply_text("Key facts updated. Thanks for the correction.")
        else:
            await message.reply_text("Could not find the summary to update.")
        return

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
        response = await route(text, chat_id=update.effective_chat.id)
        await message.reply_text(response, parse_mode="Markdown")
        # Phase 3: persist conversation turn and update in-memory cache
        chat_id = update.effective_chat.id
        await write_conversation_turn(chat_id, "user", text)
        await write_conversation_turn(chat_id, "assistant", response)
        history_cache.append(chat_id, "user", text)
        history_cache.append(chat_id, "assistant", response)
        # Check if summarization should fire (every 20 turns)
        turn_count = await get_turn_count_since_last_summary(chat_id)
        if turn_count >= SUMMARIZE_TRIGGER:
            asyncio.create_task(summarize_and_notify(chat_id, update))
    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)
        await message.reply_text("Something went wrong. Please try again.")
