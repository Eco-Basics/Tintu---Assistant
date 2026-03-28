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
    from unittest.mock import patch, AsyncMock
    from app.llm.context_manager import ContextBudgetManager
    from app.llm.conversation_state import ConversationCache

    fake_cache = ConversationCache()
    fake_cache.append(1, "user", "what is the weather?")
    fake_cache.append(1, "assistant", "I don't have weather data.")

    async def mock_fetchall(query, params):
        return []

    with patch("app.llm.context_manager.history_cache", fake_cache), \
         patch("app.llm.context_manager.fetchall", mock_fetchall):
        mgr = ContextBudgetManager(1)
        result = await mgr.assemble_context("follow up question")

    assert result["history_block"].startswith("Previous conversation:")
    assert "You: what is the weather?" in result["history_block"]
    assert "Assistant: I don't have weather data." in result["history_block"]


@pytest.mark.asyncio
async def test_extraction_calls_no_history(db):
    """Extraction intents do not receive history injection in the Ollama prompt."""
    from unittest.mock import patch, AsyncMock, call
    captured_prompts = []

    async def mock_generate(prompt, system="", **kwargs):
        captured_prompts.append(prompt)
        return "task_id: 1\ntitle: Buy groceries\ndue: \npriority: normal"

    async def mock_classify(message):
        return "create_task"

    from app.bot import router
    with patch("app.bot.router.classify", mock_classify), \
         patch("app.bot.router.generate", mock_generate), \
         patch("app.bot.router.create_task", AsyncMock(return_value=1)):
        # route() called WITHOUT chat_id (extraction path)
        await router.route("add task buy groceries")

    # The prompt used for extraction should NOT contain "Previous conversation"
    assert len(captured_prompts) >= 1
    for p in captured_prompts:
        assert "Previous conversation" not in p, f"History leaked into extraction: {p[:100]}"


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
    from unittest.mock import patch
    from app.llm.context_manager import ContextBudgetManager, BUDGET_LIMIT
    from app.llm.conversation_state import ConversationCache

    # Create a cache with many long messages
    fake_cache = ConversationCache()
    long_content = "x" * 400  # ~100 tokens per message
    for i in range(16):
        role = "user" if i % 2 == 0 else "assistant"
        fake_cache.append(42, role, long_content)

    async def mock_fetchall(query, params):
        return []

    with patch("app.llm.context_manager.history_cache", fake_cache), \
         patch("app.llm.context_manager.fetchall", mock_fetchall):
        mgr = ContextBudgetManager(42)
        result = await mgr.assemble_context("new message")

    total = result["tokens_used"]
    assert total <= BUDGET_LIMIT, f"tokens_used {total} exceeds BUDGET_LIMIT {BUDGET_LIMIT}"


@pytest.mark.asyncio
async def test_history_trim_oldest_first(db):
    """When budget exceeded, oldest turns are removed before newer ones."""
    from unittest.mock import patch
    from app.llm.context_manager import ContextBudgetManager
    from app.llm.conversation_state import ConversationCache

    fake_cache = ConversationCache()
    # Fill with large messages that will exceed HISTORY_BUDGET
    big_content = "w" * 1200  # ~300 tokens per message
    for i in range(16):
        role = "user" if i % 2 == 0 else "assistant"
        fake_cache.append(55, role, f"[turn {i}] {big_content}")

    async def mock_fetchall(query, params):
        return []

    with patch("app.llm.context_manager.history_cache", fake_cache), \
         patch("app.llm.context_manager.fetchall", mock_fetchall):
        mgr = ContextBudgetManager(55)
        result = await mgr.assemble_context("current question")

    history_block = result["history_block"]
    if history_block:
        # Most recent turns should survive; oldest should be gone
        assert "[turn 15]" in history_block or "[turn 14]" in history_block, \
            "Newest turns should be present after trim"
        assert "[turn 0]" not in history_block, "Oldest turn should have been trimmed"


@pytest.mark.asyncio
async def test_active_tasks_injected(db):
    """assemble_context() includes up to 5 active/inbox tasks in tasks_block."""
    from unittest.mock import patch
    from app.llm.context_manager import ContextBudgetManager
    from app.llm.conversation_state import ConversationCache

    fake_cache = ConversationCache()  # no history
    mock_tasks = [
        {"title": "Review pitch deck"},
        {"title": "Send invoice to client"},
        {"title": "Fix login bug"},
    ]

    async def mock_fetchall(query, params):
        return mock_tasks

    with patch("app.llm.context_manager.history_cache", fake_cache), \
         patch("app.llm.context_manager.fetchall", mock_fetchall):
        mgr = ContextBudgetManager(77)
        result = await mgr.assemble_context("what should I work on?")

    tasks_block = result["tasks_block"]
    assert "Active tasks:" in tasks_block
    assert "Review pitch deck" in tasks_block
    assert "Send invoice to client" in tasks_block
    assert "Fix login bug" in tasks_block


# ── Plan 03-04: Summarization (PERS-03) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_summarize_fires_at_20_turns(db):
    """After 20 conversation_turns rows since last summary, turn count >= 20."""
    from unittest.mock import patch
    from app.memory.summarizer import get_turn_count_since_last_summary

    # Insert 20 turns directly into in-memory DB
    for i in range(20):
        role = "user" if i % 2 == 0 else "assistant"
        await db.execute(
            "INSERT INTO conversation_turns (chat_id, role, content) VALUES (?, ?, ?)",
            (11, role, f"message {i}"),
        )
    await db.commit()

    async def mock_fetchone(query, params):
        # No prior summary
        if "conversation_summaries" in query:
            return None
        if "COUNT" in query:
            return {"cnt": 20}
        return None

    async def mock_fetchall(query, params):
        return []

    with patch("app.memory.summarizer.fetchone", mock_fetchone), \
         patch("app.memory.summarizer.fetchall", mock_fetchall):
        count = await get_turn_count_since_last_summary(11)

    assert count >= 20, f"Expected >= 20 turns, got {count}"


@pytest.mark.asyncio
async def test_summarize_command_triggers(db):
    """route('/summarize') returns acknowledgement string."""
    from unittest.mock import patch, AsyncMock

    async def mock_classify(message):
        return "summarize"

    from app.bot import router
    with patch("app.bot.router.classify", mock_classify):
        result = await router.route("/summarize", chat_id=None)

    assert "summariz" in result.lower() or "summary" in result.lower(), \
        f"Expected summarization acknowledgement, got: {result}"


@pytest.mark.asyncio
async def test_summary_sent_to_user():
    """summarize_and_notify sends summary text to user via Telegram."""
    from unittest.mock import patch, AsyncMock, MagicMock

    mock_send = AsyncMock()
    mock_bot = MagicMock()
    mock_bot.send_message = mock_send

    mock_update = MagicMock()
    mock_update.get_bot = MagicMock(return_value=mock_bot)

    async def mock_generate_session_summary(chat_id):
        return ("Session was productive.", "Decided to deploy on Friday.", 42)

    from app.bot.handlers import summarize_and_notify
    with patch("app.bot.handlers.generate_session_summary", mock_generate_session_summary):
        await summarize_and_notify(99, mock_update)

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args
    text_arg = call_kwargs[1].get("text") or (call_kwargs[0][1] if call_kwargs[0] else "")
    assert "Session was productive" in text_arg or "summary" in text_arg.lower()


@pytest.mark.asyncio
async def test_keyfacts_correction_updates_db(db):
    """apply_key_facts_correction updates key_facts in the most recent summary row."""
    from unittest.mock import patch
    from app.memory.summarizer import apply_key_facts_correction

    # Insert a summary row
    await db.execute(
        "INSERT INTO conversation_summaries (date, summary) VALUES ('2026-03-28', 'test summary')",
    )
    await db.commit()
    async with db.execute("SELECT last_insert_rowid() AS id") as cur:
        row = await cur.fetchone()
    summary_id = row[0]

    async def mock_fetchone(query, params):
        if "SELECT id" in query:
            return {"id": summary_id}
        return None

    async def mock_execute(query, params):
        # Verify the UPDATE is called with correct params
        assert "UPDATE conversation_summaries SET key_facts" in query
        assert params[0] == "Actually we decided Thursday, not Friday."
        assert params[1] == summary_id
        return 1

    with patch("app.memory.summarizer.fetchone", mock_fetchone), \
         patch("app.memory.summarizer.execute", mock_execute):
        result = await apply_key_facts_correction(summary_id, "Actually we decided Thursday, not Friday.")

    assert result is True


# ── Plan 03-05: Session continuity (CTX-03) ──────────────────────────────────

@pytest.mark.asyncio
async def test_continuity_signal_resume(db):
    """When no turns but prior summary exists, load_conversation_state returns signal='resume'."""
    from unittest.mock import patch
    from app.llm.conversation_state import load_conversation_state, ConversationCache

    fresh_cache = ConversationCache()

    async def mock_fetchall(query, params):
        return []  # No conversation_turns

    async def mock_fetchone(query, params):
        return {"summary": "Last session: worked on deployment plan."}  # Summary exists

    with patch("app.llm.conversation_state.fetchall", mock_fetchall), \
         patch("app.llm.conversation_state.fetchone", mock_fetchone), \
         patch("app.llm.conversation_state.history_cache", fresh_cache):
        result = await load_conversation_state(12345)

    assert result["signal"] == "resume", f"Expected 'resume', got {result['signal']}"
    assert result["summary_text"] == "Last session: worked on deployment plan."
    assert result["messages"] == []


@pytest.mark.asyncio
async def test_continuity_signal_fresh(db):
    """When no turns and no summaries, load_conversation_state returns signal='fresh'."""
    from unittest.mock import patch
    from app.llm.conversation_state import load_conversation_state, ConversationCache

    fresh_cache = ConversationCache()

    async def mock_fetchall(query, params):
        return []  # No conversation_turns

    async def mock_fetchone(query, params):
        return None  # No prior summary

    with patch("app.llm.conversation_state.fetchall", mock_fetchall), \
         patch("app.llm.conversation_state.fetchone", mock_fetchone), \
         patch("app.llm.conversation_state.history_cache", fresh_cache):
        result = await load_conversation_state(99999)

    assert result["signal"] == "fresh", f"Expected 'fresh', got {result['signal']}"
    assert result["summary_text"] is None
    assert result["messages"] == []
