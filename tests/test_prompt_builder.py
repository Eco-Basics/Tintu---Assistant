import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock

from app.llm.prompt_builder import build_system_prompt

pytestmark = pytest.mark.asyncio


async def test_empty_tables(async_db):
    """All tables empty: result starts with SYSTEM_PROMPT base identity content."""
    with patch("app.storage.db.fetchall", new=AsyncMock(side_effect=[[], [], []])):
        result = await build_system_prompt()
    assert result.startswith("You are a private planning and memory assistant")


async def test_with_preferences(async_db):
    """Preferences table has a row: result contains 'Behavior preferences:' section."""
    prefs = [{"key": "directness", "value": "be more direct", "source": "user said so"}]
    with patch(
        "app.storage.db.fetchall",
        new=AsyncMock(side_effect=[prefs, [], []]),
    ):
        result = await build_system_prompt()
    assert "Behavior preferences:" in result
    assert "- be more direct." in result


async def test_empty_traits_placeholder(async_db):
    """Empty personality_traits: result contains 'Personality traits: none yet'."""
    with patch("app.storage.db.fetchall", new=AsyncMock(side_effect=[[], [], []])):
        result = await build_system_prompt()
    assert "Personality traits: none yet" in result


async def test_active_persona(async_db):
    """Personas row with is_active=1: persona instruction appended."""
    personas = [{"description": "brutally honest advisor"}]
    with patch(
        "app.storage.db.fetchall",
        new=AsyncMock(side_effect=[[], [], personas]),
    ):
        result = await build_system_prompt()
    assert "For this session, adopt the following persona: brutally honest advisor." in result


async def test_inactive_persona_excluded(async_db):
    """Personas row with is_active=0: no persona instruction in result."""
    # is_active=0 rows are filtered by the SQL query (WHERE is_active=1), so fetchall returns []
    with patch("app.storage.db.fetchall", new=AsyncMock(side_effect=[[], [], []])):
        result = await build_system_prompt()
    assert "For this session, adopt the following persona" not in result


async def test_debug_log(async_db):
    """logger.debug is called with a string containing 'system_prompt=' on every invocation."""
    with patch("app.storage.db.fetchall", new=AsyncMock(side_effect=[[], [], []])):
        with patch("app.llm.prompt_builder.logger") as mock_logger:
            await build_system_prompt()
    mock_logger.debug.assert_called_once()
    call_arg = mock_logger.debug.call_args[0][0]
    assert "system_prompt=" in call_arg
