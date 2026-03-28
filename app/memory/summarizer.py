import logging
from app.llm.ollama_client import generate
from app.storage.db import execute, fetchall, fetchone
from app.utils.time import today_str

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = """Summarize the following conversation log into a concise memory entry.

Return this exact format:
Summary: <one paragraph summary>
Topics: <comma-separated topics>
Projects: <comma-separated project names or none>
Actions: <comma-separated actions taken or none>
Decisions: <comma-separated decisions made or none>

Log:
{log}"""


async def summarize_conversation(log: str, message_range: str = "") -> int:
    prompt = SUMMARIZE_PROMPT.format(log=log)
    response = await generate(prompt)

    fields = {"summary": "", "topics": "", "projects": "", "actions": "", "decisions": ""}
    for line in response.splitlines():
        for key in fields:
            if line.lower().startswith(f"{key}:"):
                fields[key] = line.split(":", 1)[1].strip()

    if not fields["summary"]:
        fields["summary"] = response[:300]

    row_id = await execute(
        """INSERT INTO conversation_summaries
           (date, summary, topics, projects, actions, decisions, source_message_range)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            today_str(),
            fields["summary"],
            fields["topics"],
            fields["projects"],
            fields["actions"],
            fields["decisions"],
            message_range,
        ),
    )
    logger.info(f"Saved conversation summary id={row_id}")
    return row_id


# ── Phase 3 additions ─────────────────────────────────────────────────────────

KEY_FACTS_PROMPT = """From the conversation summary below, extract the most important
verbatim facts that must survive word-for-word — specific decisions made, named people,
dates, explicit preferences stated, or commitments given.

Return each fact on its own line, 3-10 facts. Be precise and literal.

Summary:
{summary}"""


async def get_turn_count_since_last_summary(chat_id: int) -> int:
    """Count conversation_turns rows since the most recent summary for this chat_id.

    If no summary exists, returns total turn count for chat_id.
    """
    last_summary = await fetchone(
        "SELECT created_at FROM conversation_summaries ORDER BY created_at DESC LIMIT 1",
        (),
    )
    if last_summary:
        count_row = await fetchone(
            "SELECT COUNT(*) AS cnt FROM conversation_turns "
            "WHERE chat_id = ? AND created_at > ?",
            (chat_id, last_summary["created_at"]),
        )
    else:
        count_row = await fetchone(
            "SELECT COUNT(*) AS cnt FROM conversation_turns WHERE chat_id = ?",
            (chat_id,),
        )
    return count_row["cnt"] if count_row else 0


async def generate_session_summary(chat_id: int) -> tuple[str, str, int]:
    """
    Fetch turns since last summary, generate narrative summary + key_facts,
    save to DB, return (summary_text, key_facts_text, row_id).
    """
    last_summary = await fetchone(
        "SELECT created_at FROM conversation_summaries ORDER BY created_at DESC LIMIT 1",
        (),
    )
    if last_summary:
        turns = await fetchall(
            "SELECT role, content FROM conversation_turns "
            "WHERE chat_id = ? AND created_at > ? ORDER BY created_at ASC",
            (chat_id, last_summary["created_at"]),
        )
    else:
        turns = await fetchall(
            "SELECT role, content FROM conversation_turns "
            "WHERE chat_id = ? ORDER BY created_at ASC",
            (chat_id,),
        )

    if not turns:
        return ("No conversation to summarize.", "", 0)

    log = "\n".join(
        f"{'User' if t['role'] == 'user' else 'Assistant'}: {t['content']}"
        for t in turns
    )
    message_range = f"{len(turns)} messages"

    # Generate narrative summary
    summary_response = await generate(SUMMARIZE_PROMPT.format(log=log))
    fields = {"summary": "", "topics": "", "projects": "", "actions": "", "decisions": ""}
    for line in summary_response.splitlines():
        for key in fields:
            if line.lower().startswith(f"{key}:"):
                fields[key] = line.split(":", 1)[1].strip()
    if not fields["summary"]:
        fields["summary"] = summary_response[:300]

    # Generate key_facts
    key_facts_response = await generate(
        KEY_FACTS_PROMPT.format(summary=fields["summary"])
    )
    key_facts = key_facts_response.strip()

    row_id = await execute(
        """INSERT INTO conversation_summaries
           (date, summary, topics, projects, actions, decisions, source_message_range, key_facts)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            today_str(),
            fields["summary"],
            fields["topics"],
            fields["projects"],
            fields["actions"],
            fields["decisions"],
            message_range,
            key_facts,
        ),
    )
    logger.info(f"Session summary saved id={row_id}, key_facts={len(key_facts)} chars")
    return (fields["summary"], key_facts, row_id)


async def apply_key_facts_correction(summary_id: int, correction_text: str) -> bool:
    """
    Update key_facts for the given summary_id with corrected text.
    Returns True if row was found and updated.
    """
    existing = await fetchone(
        "SELECT id FROM conversation_summaries WHERE id = ?", (summary_id,)
    )
    if not existing:
        logger.warning(f"Summary id={summary_id} not found for correction")
        return False
    await execute(
        "UPDATE conversation_summaries SET key_facts = ? WHERE id = ?",
        (correction_text, summary_id),
    )
    logger.info(f"key_facts corrected for summary id={summary_id}")
    return True
