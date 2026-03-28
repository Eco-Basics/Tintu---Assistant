import os
import pytest
import pytest_asyncio
import aiosqlite

# Set required env vars before any app module is imported.
# These are stubs only — tests mock the actual external calls.
os.environ.setdefault("TELEGRAM_TOKEN", "test-token-stub")
os.environ.setdefault("TELEGRAM_USER_ID", "0")

FIXTURE_SCHEMA = """
CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    source TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS personality_traits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    signal_type TEXT,
    confidence REAL DEFAULT 1.0,
    source TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    is_active INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def in_memory_db():
    async with aiosqlite.connect(":memory:") as db:
        yield db


@pytest_asyncio.fixture
async def async_db():
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(FIXTURE_SCHEMA)
        await db.commit()
        yield db


# ── Phase 3: context-budget-manager ─────────────────────────────────────────
from app.storage.models import SCHEMA as FULL_SCHEMA  # noqa: E402


@pytest_asyncio.fixture
async def db():
    """In-memory aiosqlite with full schema including conversation_turns."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.executescript(FULL_SCHEMA)
        # Additive columns for Phase 3
        for col, col_type in [("key_facts", "TEXT"), ("named_entities", "TEXT")]:
            try:
                await conn.execute(
                    f"ALTER TABLE conversation_summaries ADD COLUMN {col} {col_type}"
                )
            except Exception:
                pass
        await conn.commit()
        yield conn
