"""
context_manager.py — Token budget enforcement and context assembly for Ollama calls.

Hard limit: 8,192 tokens per Ollama call (CTX-01).
Token counting: character count // 4 (estimate; validate against prompt_eval_count in UAT).
Trim order: oldest history first — never trim system prompt or active tasks.
"""
import logging
from app.llm.conversation_state import history_cache
from app.storage.db import fetchall

logger = logging.getLogger(__name__)

BUDGET_LIMIT = 8192
RESPONSE_RESERVE = 2000
SYSTEM_PROMPT_BUDGET = 800
SUMMARY_BUDGET = 400
TASKS_BUDGET = 200
MESSAGE_BUDGET = 500
# Available for rolling history
HISTORY_BUDGET = (
    BUDGET_LIMIT
    - RESPONSE_RESERVE
    - SYSTEM_PROMPT_BUDGET
    - SUMMARY_BUDGET
    - TASKS_BUDGET
    - MESSAGE_BUDGET
)  # = 4292


def count_tokens(text: str) -> int:
    """Estimate token count: character count // 4."""
    return len(text) // 4


class ContextBudgetManager:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id

    async def assemble_context(self, message: str) -> dict:
        """
        Build history and task context blocks respecting token budget.

        Returns:
            history_block: str — prepend to user message before Ollama call ("" if no history)
            tasks_block: str — append to prompt for task awareness ("" if no tasks)
            tokens_used: int — estimated tokens consumed by both blocks
        """
        history_block = self._build_history_block()
        tasks_block = await self._build_tasks_block()
        history_block = self._trim_history_to_budget(history_block)

        tokens_used = count_tokens(history_block) + count_tokens(tasks_block)
        logger.debug(
            "Context assembled chat_id=%s: history=%dt tasks=%dt total=%dt",
            self.chat_id,
            count_tokens(history_block),
            count_tokens(tasks_block),
            tokens_used,
        )
        return {
            "history_block": history_block,
            "tasks_block": tasks_block,
            "tokens_used": tokens_used,
        }

    def _build_history_block(self) -> str:
        messages = history_cache.get(self.chat_id)
        if not messages:
            return ""
        lines = []
        for msg in messages:
            label = "You" if msg["role"] == "user" else "Assistant"
            lines.append(f"{label}: {msg['content']}")
        return "Previous conversation:\n" + "\n".join(lines) + "\n\n"

    def _trim_history_to_budget(self, history_block: str) -> str:
        if not history_block or count_tokens(history_block) <= HISTORY_BUDGET:
            return history_block
        messages = list(history_cache.get(self.chat_id))
        while messages and count_tokens(history_block) > HISTORY_BUDGET:
            # Drop oldest user+assistant pair (2 messages)
            messages = messages[2:]
            if not messages:
                return ""
            lines = []
            for msg in messages:
                label = "You" if msg["role"] == "user" else "Assistant"
                lines.append(f"{label}: {msg['content']}")
            history_block = "Previous conversation:\n" + "\n".join(lines) + "\n\n"
        if messages:
            logger.warning(
                "History trimmed for chat_id=%s: %d messages kept", self.chat_id, len(messages)
            )
        return history_block

    async def _build_tasks_block(self) -> str:
        tasks = await fetchall(
            "SELECT title FROM tasks "
            "WHERE status IN ('inbox', 'active') "
            "ORDER BY priority DESC, created_at DESC "
            "LIMIT 5",
            (),
        )
        if not tasks:
            return ""
        lines = [f"{i + 1}. {t['title']}" for i, t in enumerate(tasks)]
        return "Active tasks:\n" + "\n".join(lines) + "\n"
