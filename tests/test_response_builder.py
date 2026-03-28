import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.llm.response_builder import build_answer


@pytest.mark.asyncio
async def test_dynamic_prompt_injected():
    """build_answer() with chat_id must call ContextBudgetManager.assemble_context() and pass result to generate()."""
    mock_ctx = MagicMock()
    mock_ctx.assemble_context = AsyncMock(return_value={
        "history_block": "Prior: hello\n\n",
        "tasks_block": "",
    })

    with patch(
        "app.llm.response_builder.ContextBudgetManager",
        return_value=mock_ctx,
    ), patch(
        "app.llm.response_builder.generate",
        new=AsyncMock(return_value="MOCK_RESPONSE"),
    ) as mock_generate:
        result = await build_answer("hello", chat_id=42)

    mock_ctx.assemble_context.assert_called_once_with("hello")
    mock_generate.assert_called_once()
    args, _kwargs = mock_generate.call_args
    assert "hello" in args[0], f"generate() prompt missing user message: {args[0]!r}"
    assert result == "MOCK_RESPONSE"
