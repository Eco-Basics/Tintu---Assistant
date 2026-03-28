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
