import logging
from app.llm.prompts import SYSTEM_PROMPT
from app.storage.db import fetchall

logger = logging.getLogger(__name__)


async def build_system_prompt() -> str:
    sections = [SYSTEM_PROMPT]

    prefs = await fetchall("SELECT key, value FROM preferences ORDER BY updated_at DESC")
    if prefs:
        lines = "\n".join(f"- {row['value']}." for row in prefs)
        sections.append(f"Behavior preferences:\n{lines}")

    traits = await fetchall("SELECT key, value FROM personality_traits")
    if traits:
        lines = "\n".join(f"- {row['key']}: {row['value']}" for row in traits)
        sections.append(f"Personality traits:\n{lines}")
    else:
        sections.append("Personality traits: none yet")

    personas = await fetchall(
        "SELECT description FROM personas WHERE is_active=1 LIMIT 1"
    )
    if personas:
        sections.append(
            f"For this session, adopt the following persona: {personas[0]['description']}."
        )

    assembled = "\n\n".join(sections)
    logger.debug(f"system_prompt=\n{assembled}")
    return assembled
