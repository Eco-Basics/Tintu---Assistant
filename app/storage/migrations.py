import logging
from app.storage.db import get_db
from app.storage.models import SCHEMA

logger = logging.getLogger(__name__)


async def run_migrations():
    logger.info("Running database migrations...")
    async with await get_db() as db:
        await db.executescript(SCHEMA)
        # Additive: add key_facts and named_entities to conversation_summaries
        for col, col_type in [("key_facts", "TEXT"), ("named_entities", "TEXT")]:
            try:
                await db.execute(
                    f"ALTER TABLE conversation_summaries ADD COLUMN {col} {col_type}"
                )
            except Exception:
                pass  # Column already exists — safe to ignore
        await db.commit()
    logger.info("Database ready.")
