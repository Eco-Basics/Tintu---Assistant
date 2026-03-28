import pytest
from unittest.mock import AsyncMock, patch

REFUSAL_SUBSTRING = "can't"  # Update to exact REFUSAL_MESSAGE after Task 2 is written


@pytest.mark.asyncio
async def test_code_refusal(monkeypatch):
    monkeypatch.setattr("app.bot.router.classify", AsyncMock(return_value="answer"))
    mock_generate = AsyncMock(return_value="some response")
    monkeypatch.setattr("app.bot.router.generate", mock_generate)
    from app.bot.router import route
    result = await route("write a Python function to sort a list")
    assert REFUSAL_SUBSTRING in result.lower()
    mock_generate.assert_not_called()


@pytest.mark.asyncio
async def test_math_refusal(monkeypatch):
    monkeypatch.setattr("app.bot.router.classify", AsyncMock(return_value="answer"))
    mock_generate = AsyncMock(return_value="some response")
    monkeypatch.setattr("app.bot.router.generate", mock_generate)
    from app.bot.router import route
    result = await route("solve this equation: 2x + 5 = 11")
    assert REFUSAL_SUBSTRING in result.lower()
    mock_generate.assert_not_called()


@pytest.mark.asyncio
async def test_research_refusal(monkeypatch):
    monkeypatch.setattr("app.bot.router.classify", AsyncMock(return_value="answer"))
    mock_generate = AsyncMock(return_value="some response")
    monkeypatch.setattr("app.bot.router.generate", mock_generate)
    from app.bot.router import route
    result = await route("what is the latest news today about tech")
    assert REFUSAL_SUBSTRING in result.lower()
    mock_generate.assert_not_called()


@pytest.mark.asyncio
async def test_non_answer_bypass(monkeypatch):
    """set_reminder intent: refusal check must not fire even if message contains code words."""
    monkeypatch.setattr("app.bot.router.classify", AsyncMock(return_value="set_reminder"))
    mock_generate = AsyncMock(return_value="when: tomorrow 9am\ntitle: code review\nnote: ")
    monkeypatch.setattr("app.bot.router.generate", mock_generate)
    monkeypatch.setattr("app.bot.router.today_str", lambda: "2026-03-28")
    monkeypatch.setattr("app.bot.router.create_reminder", AsyncMock(return_value=1))
    from app.bot.router import route
    result = await route("remind me to code tonight at 9pm")
    assert REFUSAL_SUBSTRING not in result.lower()


@pytest.mark.asyncio
async def test_retrieval_bypass(monkeypatch):
    """retrieval_query intent: must bypass refusal check entirely."""
    monkeypatch.setattr("app.bot.router.classify", AsyncMock(return_value="retrieval_query"))
    mock_build = AsyncMock(return_value="Here is what I found...")
    monkeypatch.setattr("app.bot.router.build_retrieval_answer", mock_build)
    from app.bot.router import route
    result = await route("what did I say about the project last week")
    mock_build.assert_called_once()
    assert REFUSAL_SUBSTRING not in result.lower()
