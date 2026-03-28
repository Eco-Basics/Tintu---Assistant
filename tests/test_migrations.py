import pytest
import pytest_asyncio
import aiosqlite
from app.storage.models import SCHEMA


@pytest.mark.asyncio
async def test_personality_traits_table():
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='personality_traits'"
        ) as cursor:
            row = await cursor.fetchone()
    assert row is not None, "personality_traits table was not created by migration"


@pytest.mark.asyncio
async def test_personas_table():
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='personas'"
        ) as cursor:
            row = await cursor.fetchone()
    assert row is not None, "personas table was not created by migration"


@pytest.mark.asyncio
async def test_migration_idempotent():
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        # Run a second time — must not raise
        await db.executescript(SCHEMA)


@pytest.mark.asyncio
async def test_existing_rows_preserved():
    async with aiosqlite.connect(":memory:") as db:
        # Run initial migration to create preferences table
        await db.executescript(SCHEMA)
        # Insert a row
        await db.execute(
            "INSERT INTO preferences (key, value, source) VALUES (?, ?, ?)",
            ("response_tone", "direct", "test"),
        )
        await db.commit()
        # Run migration again (idempotent)
        await db.executescript(SCHEMA)
        # Row must still exist
        async with db.execute("SELECT COUNT(*) FROM preferences") as cursor:
            count_row = await cursor.fetchone()
    assert count_row[0] == 1, "Existing preferences rows were lost during migration"
