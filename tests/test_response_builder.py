import pytest
from unittest.mock import AsyncMock, patch

from app.llm.response_builder import build_answer


@pytest.mark.asyncio
async def test_dynamic_prompt_injected():
    """build_answer() must pass build_system_prompt()'s return value as system= to generate()."""
    sentinel = "MOCK_SYSTEM_PROMPT"

    with patch(
        "app.llm.response_builder.build_system_prompt",
        new=AsyncMock(return_value=sentinel),
    ) as mock_build, patch(
        "app.llm.response_builder.generate",
        new=AsyncMock(return_value="MOCK_RESPONSE"),
    ) as mock_generate:
        result = await build_answer("hello")

    mock_build.assert_called_once()
    mock_generate.assert_called_once()
    _args, kwargs = mock_generate.call_args
    assert kwargs.get("system") == sentinel, (
        f"generate() called with system={kwargs.get('system')!r}, expected {sentinel!r}"
    )
    assert result == "MOCK_RESPONSE"
