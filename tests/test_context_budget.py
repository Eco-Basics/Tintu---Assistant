"""Phase 3 — Context Budget Manager tests.

All tests start as NotImplementedError stubs (red). Plans 03-02 through 03-05
replace each stub with real assertions.
"""
import pytest
import pytest_asyncio


# ── Plan 03-02: History cache (PERS-02) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_conversation_turns_table(db):
    """conversation_turns table accepts user/assistant rows."""
    await db.execute(
        "INSERT INTO conversation_turns (chat_id, role, content) VALUES (?, ?, ?)",
        (12345, "user", "hello")
    )
    await db.execute(
        "INSERT INTO conversation_turns (chat_id, role, content) VALUES (?, ?, ?)",
        (12345, "assistant", "hi there")
    )
    await db.commit()
    async with db.execute(
        "SELECT role, content FROM conversation_turns WHERE chat_id = ? ORDER BY id",
        (12345,)
    ) as cur:
        rows = await cur.fetchall()
    assert len(rows) == 2
    assert rows[0][0] == "user"
    assert rows[1][0] == "assistant"
    assert rows[1][1] == "hi there"


@pytest.mark.asyncio
async def test_conversation_summaries_columns(db):
    """conversation_summaries has key_facts and named_entities columns."""
    async with db.execute("PRAGMA table_info(conversation_summaries)") as cur:
        rows = await cur.fetchall()
    col_names = [r[1] for r in rows]
    assert "key_facts" in col_names, f"key_facts missing, got: {col_names}"
    assert "named_entities" in col_names, f"named_entities missing, got: {col_names}"


@pytest.mark.asyncio
async def test_history_append_and_cap(db):
    """In-memory history cache caps at 16 messages (8 turns) per PERS-02."""
    from app.llm.conversation_state import ConversationCache
    cache = ConversationCache()
    for i in range(10):
        cache.append(999, "user", f"msg {i}")
        cache.append(999, "assistant", f"reply {i}")
    msgs = cache.get(999)
    assert len(msgs) == 16, f"Expected 16, got {len(msgs)}"
    # Oldest dropped: first entry should be msg 2 (index 0 after trim)
    assert msgs[0]["content"] == "msg 2"
    assert msgs[-1]["content"] == "reply 9"


@pytest.mark.asyncio
async def test_history_prepend_format(db):
    """assemble_context() produces 'Previous conversation:\\nYou: ...\\nAssistant: ...' block."""
    raise NotImplementedError


@pytest.mark.asyncio
async def test_extraction_calls_no_history(db):
    """Extraction intents (create_task, set_reminder, update_preference, record_decision,
    complete_task) do not receive history injection in the Ollama prompt."""
    raise NotImplementedError


@pytest.mark.asyncio
async def test_reload_on_startup(db):
    """load_conversation_state() populates in-memory cache from conversation_turns rows."""
    import asyncio
    from unittest.mock import patch, AsyncMock
    from app.llm.conversation_state import ConversationCache, load_conversation_state

    rows_data = [
        {"role": "user", "content": "first message"},
        {"role": "assistant", "content": "first reply"},
        {"role": "user", "content": "second message"},
    ]

    async def mock_fetchall(query, params):
        return rows_data

    fresh_cache = ConversationCache()
    with patch("app.llm.conversation_state.fetchall", mock_fetchall), \
         patch("app.llm.conversation_state.history_cache", fresh_cache):
        result = await load_conversation_state(12345)

    assert len(result) == 3
    assert fresh_cache.get(12345) == rows_data


# ── Plan 03-03: Token budget (CTX-01, CTX-02) ────────────────────────────────

@pytest.mark.asyncio
async def test_token_budget_under_8192(db):
    """assemble_context() total token estimate <= 8192 regardless of history length."""
    raise NotImplementedError


@pytest.mark.asyncio
async def test_history_trim_oldest_first(db):
    """When budget exceeded, oldest turns are removed before newer ones."""
    raise NotImplementedError


@pytest.mark.asyncio
async def test_active_tasks_injected(db):
    """assemble_context() includes up to 5 active/inbox tasks in context block."""
    raise NotImplementedError


# ── Plan 03-04: Summarization (PERS-03) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_summarize_fires_at_20_turns(db):
    """After 20 conversation_turns rows since last summary, summarization is triggered."""
    raise NotImplementedError


@pytest.mark.asyncio
async def test_summarize_command_triggers(db):
    """route('/summarize') returns acknowledgement and triggers summarization."""
    raise NotImplementedError


@pytest.mark.asyncio
async def test_summary_sent_to_user():
    """summarize_and_notify() sends summary text to user via Telegram."""
    raise NotImplementedError


@pytest.mark.asyncio
async def test_keyfacts_correction_updates_db(db):
    """A correction reply updates the key_facts column in the most recent
    conversation_summaries row."""
    raise NotImplementedError


# ── Plan 03-05: Session continuity (CTX-03) ──────────────────────────────────

@pytest.mark.asyncio
async def test_continuity_signal_resume(db):
    """When turns exist in DB for chat_id, load_conversation_state() returns
    signal='resume' with the last summary text."""
    raise NotImplementedError


@pytest.mark.asyncio
async def test_continuity_signal_fresh(db):
    """When no turns and no summaries exist for chat_id, load_conversation_state()
    returns signal='fresh'."""
    raise NotImplementedError
