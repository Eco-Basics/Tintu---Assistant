"""
conversation_state.py — In-memory history cache + DB persistence for conversation turns.

ConversationCache: dict[chat_id -> list[{"role": str, "content": str}]]
Cap: 16 messages per chat_id (8 user + 8 assistant turns per PERS-02).
DB source of truth: conversation_turns table written on every exchange.
"""
import logging
from collections import defaultdict
from app.storage.db import execute, fetchall

logger = logging.getLogger(__name__)

MAX_MESSAGES = 16  # 8 turns = 16 messages (user + assistant per turn)


class ConversationCache:
    def __init__(self):
        self._data: dict[int, list[dict]] = defaultdict(list)

    def append(self, chat_id: int, role: str, content: str) -> None:
        """Add a message and enforce cap of MAX_MESSAGES."""
        self._data[chat_id].append({"role": role, "content": content})
        if len(self._data[chat_id]) > MAX_MESSAGES:
            self._data[chat_id] = self._data[chat_id][-MAX_MESSAGES:]

    def get(self, chat_id: int) -> list[dict]:
        """Return current history for chat_id (may be empty list)."""
        return list(self._data[chat_id])

    def set(self, chat_id: int, messages: list[dict]) -> None:
        """Replace history for chat_id (used during startup reload)."""
        self._data[chat_id] = list(messages[-MAX_MESSAGES:])

    def clear(self, chat_id: int) -> None:
        self._data[chat_id] = []


# Module-level singleton used by handlers.py and context_manager.py
history_cache = ConversationCache()


async def write_conversation_turn(chat_id: int, role: str, content: str) -> int:
    """Write a single turn to conversation_turns table. Returns rowid."""
    return await execute(
        "INSERT INTO conversation_turns (chat_id, role, content, created_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        (chat_id, role, content),
    )


async def load_conversation_state(chat_id: int) -> list[dict]:
    """
    Reload last 8 turns (16 messages) from DB for chat_id into history_cache.
    Returns the loaded messages (may be empty if no prior turns exist).
    Called once on startup in main.py post_init.
    """
    rows = await fetchall(
        """SELECT role, content FROM (
               SELECT role, content, created_at
               FROM conversation_turns
               WHERE chat_id = ?
               ORDER BY created_at DESC
               LIMIT ?
           ) sub ORDER BY created_at ASC""",
        (chat_id, MAX_MESSAGES),
    )
    messages = [{"role": r["role"], "content": r["content"]} for r in rows]
    if messages:
        history_cache.set(chat_id, messages)
        logger.info(f"Loaded {len(messages)} messages from DB for chat_id={chat_id}")
    else:
        logger.info(f"No prior conversation turns found for chat_id={chat_id}")
    return messages
