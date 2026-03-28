import os
import pytest
import pytest_asyncio
import aiosqlite

# Set required env vars before any app module is imported.
# These are stubs only — tests mock the actual external calls.
os.environ.setdefault("TELEGRAM_TOKEN", "test-token-stub")
os.environ.setdefault("TELEGRAM_USER_ID", "0")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def in_memory_db():
    async with aiosqlite.connect(":memory:") as db:
        yield db
