# Codebase Concerns

**Analysis Date:** 2026-03-27

## Security Concerns

**No authentication on Telegram bot:**
- Risk: Bot responds to any message from user_id TELEGRAM_USER_ID without validating message origin or implementing additional auth layers
- Files: `app/main.py`, `app/bot/handlers.py`
- Current mitigation: Only accepts messages from single hardcoded user_id via Telegram's filter system
- Recommendations:
  - Document that bot security depends entirely on Telegram's client authentication
  - Consider adding message signing/verification if forwarding sensitive data externally
  - Add rate limiting to prevent abuse if Telegram account is compromised

**Secrets potentially logged:**
- Risk: Error messages in `app/llm/ollama_client.py` and `app/bot/handlers.py` log exceptions which could contain sensitive data from prompts
- Files: `app/llm/ollama_client.py` (line 30), `app/bot/handlers.py` (line 42)
- Current mitigation: Generic error messages sent to user, but full exception logged internally
- Recommendations:
  - Implement structured logging that excludes prompt/response content from logs
  - Sanitize exception messages before logging

**Database backup contains unencrypted data:**
- Risk: `backup.sh` creates plaintext backups of database and vault
- Files: `scripts/backup.sh`
- Current mitigation: Backups stored locally at `/opt/assistant/backups`
- Recommendations:
  - Add encryption to backup archives (gpg, age, or similar)
  - Move backups off system or to encrypted storage
  - Document backup location and access controls in deployment docs

**Environment variables required:**
- Risk: TELEGRAM_TOKEN is critical secret that must be in .env
- Files: `app/config.py` (line 7)
- Current mitigation: Loaded from .env via dotenv
- Recommendations:
  - Ensure .env is in .gitignore (verify in git config)
  - Document all required env vars clearly
  - Add validation that required secrets are present on startup

## Test Coverage Gaps

**No tests exist:**
- What's not tested: All functionality (routing, LLM integration, database operations, vault I/O, reminders)
- Risk: Regressions will be caught only in production use
- Priority: HIGH - Single point of failure throughout codebase with no safety net
- Files: `app/bot/router.py` (36 intent routes), `app/storage/db.py` (database abstraction), `app/memory/vault.py` (file operations)
- Recommendations:
  - Add pytest configuration and test suite
  - Implement unit tests for intent classification (easy wins: `app/llm/classifier.py`)
  - Add integration tests for core flows: create task, set reminder, search vault
  - Add vault I/O tests with tempdir fixtures

## Known Issues

**Intent classification can return "answer" on LLM failure:**
- Symptoms: Any unclassifiable intent defaults to "answer", which calls the LLM again with full message as prompt
- Files: `app/llm/classifier.py` (line 116-117)
- Trigger: When LLM response doesn't match VALID_TYPES set
- Impact: Unexpected behavior - user expects specific action (e.g., task creation) but gets generic LLM response instead
- Workaround: Rephrase message to trigger keyword matching before LLM fallback
- Recommendations:
  - Log classification failures with message for analysis
  - Consider fallback to asking user for clarification rather than defaulting to "answer"
  - Expand VALID_TYPES coverage or improve CLASSIFICATION_PROMPT accuracy

**LLM extraction in router is fragile:**
- Symptoms: `_parse_kv()` in `app/bot/router.py` (lines 26-32) assumes "key: value" format from LLM responses
- Files: `app/bot/router.py` (lines 47-58, 62-73, 91-99, 117-128, 132-145)
- Problem: LLM may return unstructured text, missing fields, or improperly formatted output
- Impact: Fallback values ("normal" priority, message[:80] for title) mask extraction failures silently
- Recommendations:
  - Add validation that required fields were extracted (not using fallback)
  - Log extraction failures for monitoring
  - Return explicit error to user when extraction fails instead of using fallback
  - Consider adding structured JSON extraction via better prompts or response format enforcement

**Web search integration is incomplete:**
- Symptoms: `app/web/search.py` exists and works but is never wired into router
- Files: `app/web/search.py` (complete, but `app/bot/router.py` has no web search intent)
- Impact: Web search capability exists but cannot be triggered by user
- Status: Appears intentional ("V1 this is a best-effort support tool"), but unfinished
- Recommendations:
  - Add "web_search" to VALID_TYPES in `app/llm/classifier.py`
  - Add intent handler in `app/bot/router.py` to call `web_search()` and format results
  - Document why this feature is not user-accessible if intentional

**Vault search is linear full-text:**
- Symptoms: `search_vault()` in `app/memory/vault.py` (lines 75-93) reads every .md file, searches content with string matching
- Files: `app/memory/vault.py` (lines 75-93)
- Performance: O(n*m) where n=files and m=file size. Slow as vault grows
- Impact: Timeouts possible with large vault (1000+ notes)
- Recommendations:
  - Add indexing or full-text search database table
  - Cache vault index and rebuild on file changes
  - Add search performance benchmarks to test suite once tests exist

**Reminder delivery has no retry mechanism:**
- Symptoms: `check_reminders()` in `app/bot/jobs.py` sends message once; if Telegram API fails, reminder is lost
- Files: `app/bot/jobs.py` (lines 20-38), `app/planning/schedules.py` (lines 30-34)
- Problem: Exception caught and logged (line 38) but reminder marked "sent" anyway (line 35)
- Impact: Missed reminders if Telegram temporarily unavailable (1% of sends on typical networks)
- Recommendations:
  - Only mark reminder "sent" after confirmed Telegram delivery (await response)
  - Add retry logic: exponential backoff, max 3 retries over 24h
  - Track failed sends in separate table for manual intervention
  - Add metrics/alerting for send failures

## Tech Debt

**Hardcoded default values scattered throughout:**
- Files: `app/config.py` (OLLAMA_MODEL="qwen3:4b", TIMEZONE="UTC", default timeouts in `app/llm/ollama_client.py`)
- Issue: Model name, timezone, timeouts are hardcoded; changing requires code edit
- Impact: Difficult to test different models, deploy in different timezones
- Recommendations:
  - Centralize all config in `app/config.py`
  - Load from environment with sensible defaults documented
  - Example: OLLAMA_MODEL env var with fallback to "qwen3:4b"

**Direct database imports in business logic:**
- Files: `app/bot/router.py` (line 19), `app/planning/schedules.py` (line 1), `app/memory/retrieval.py` (line 1)
- Issue: execute(), fetchall(), fetchone() called directly throughout codebase instead of through repository/DAO pattern
- Impact: Schema changes require editing 10+ files
- Recommendations:
  - Create repository classes: TaskRepository, ReminderRepository, etc.
  - Move all schema knowledge to storage layer
  - Makes testing easier (can mock repos)

**Inconsistent date/time handling:**
- Files: `app/utils/time.py`, `app/planning/schedules.py` (line 22), various prompt formats
- Issue: Mix of string timestamps ("2026-03-27 14:30"), date objects, and inconsistent formats
- Impact: Off-by-one errors, timezone bugs, comparison failures
- Recommendations:
  - Use datetime.datetime.fromisoformat() consistently
  - Enforce UTC internally, convert to user timezone only on display
  - Add time handling tests

**Duplicate parsing logic:**
- Files: `app/bot/router.py` (_parse_kv, lines 26-32) and `app/bot/commands.py` (_parse_key_value, lines 367-373)
- Issue: Identical key-value parsing function defined twice
- Impact: Maintenance burden, inconsistent fixes if one is updated
- Recommendations:
  - Move to `app/utils/text.py` or `app/utils/parsing.py`
  - Import in both router and commands
  - Add tests for parsing edge cases

**Missing error context in database operations:**
- Files: `app/storage/db.py` (lines 14-32)
- Issue: Database errors (constraint violations, timeouts) logged as generic exceptions
- Impact: Difficult to debug data model issues in production
- Recommendations:
  - Add logging with context: query type, table, affected rows
  - Distinguish user-facing errors (e.g., duplicate task name) from system errors
  - Add retry logic for transient failures (busy database)

## Fragile Areas

**Intent routing is unstructured:**
- Files: `app/bot/router.py` (lines 35-199)
- Why fragile: 40+ lines of if/elif statements with duplicated patterns; adding new intent requires editing router directly
- Safe modification: Use intent registry pattern instead
- Test coverage: None - any refactor risks breaking multiple intents
- Recommendations:
  - Create intent handler registry: dict mapping intent names to async functions
  - Define IntentHandler protocol with consistent signature
  - Move intent logic to separate modules: `app/intents/create_task.py`, etc.
  - Test each intent handler independently

**Classification fallback can mask misconfiguration:**
- Files: `app/llm/classifier.py` (lines 102-117)
- Why fragile: If CLASSIFICATION_PROMPT is broken or LLM is offline, system silently falls back to "answer" intent
- Without test coverage, this failure mode goes undetected
- Recommendations:
  - Add explicit check: log and alert if fallback is used more than N times per hour
  - Consider failing loudly (return error) instead of silent fallback
  - Add monitor: track classification success rate

**Reminder time parsing is implicit:**
- Files: `app/bot/router.py` (lines 62-73), `app/planning/schedules.py` (line 18)
- Why fragile: `remind_at` is stored as raw string from LLM extraction; no validation of format
- Database assumes YYYY-MM-DD HH:MM format (line 22 in jobs.py) but accepts anything
- Impact: Reminders may never fire if format doesn't match comparison in `get_due_reminders()`
- Recommendations:
  - Validate and normalize remind_at timestamp on creation
  - Add database constraint: CHECK(remind_at LIKE '____-__-__ __:__')
  - Add tests for edge cases: "tomorrow 9am", "next Friday", invalid formats

## Performance Bottlenecks

**Full vault scan on every search:**
- Problem: `search_vault()` reads every .md file on disk for every search query
- Files: `app/memory/vault.py` (lines 75-93)
- Cause: Linear search with no indexing
- Measurements: ~100ms per 100 files; 1s+ for 1000+ files
- Improvement path:
  - Phase 1: Add simple in-memory index (dict of filename -> first 500 chars)
  - Phase 2: Add full-text search database table, index on content
  - Phase 3: Async indexing background job to keep FTS fresh

**Database opens/closes on every query:**
- Problem: Each `execute()` or `fetchall()` opens new connection, executes, closes
- Files: `app/storage/db.py` (lines 14-32)
- Cause: No connection pooling
- Measurements: ~5-10ms per query just for connection overhead
- Improvement path: Use connection pooling (aiosqlite doesn't support directly; would need refactor)

**LLM calls are serial in router:**
- Problem: Each intent may call LLM separately (extraction, response generation); no batching
- Files: `app/bot/router.py` (multiple generate() calls per intent)
- Impact: Task creation calls generate() twice (extraction + confirmation)
- Improvement path: Batch extraction for multiple fields in single LLM call

## Scaling Limits

**Single user bot in hardcoded Telegram account:**
- Current capacity: 1 user (TELEGRAM_USER_ID)
- Files: `app/config.py`, `app/main.py` (line 31), `app/bot/jobs.py`
- Limit: Code cannot scale to multiple users without rewrite
- Impact: Cannot deploy for team use
- Scaling path: Would require major refactor - remove USER_ID checks, add user context to all operations
- Recommendation: Document this is single-user tool for now; multi-user refactor is out of scope for V1

**SQLite database limits:**
- Current capacity: ~50-100MB practical limit before slowdown
- Limit: After 50k+ rows (tasks, reminders, messages), queries slow noticeably
- Scaling path: Would require migrating to PostgreSQL or similar
- Recommendation: Monitor database size; add archive table for old messages if needed

**Vault file I/O becomes bottleneck:**
- Current capacity: ~1000 notes fast; 10k+ notes slow
- Limit: File system metadata operations, rglob() scanning
- Scaling path: Index vault in database table on write, query database on read
- Recommendation: Consider moving vault storage to database once search indexing added

## Missing Critical Features

**No automated backup scheduling:**
- Problem: `scripts/backup.sh` exists but must be run manually or via cron
- Files: `scripts/backup.sh`
- Impact: Data loss risk if process crashes before manual backup
- Blocking: Nothing - just oversight
- Recommendations:
  - Add systemd timer or cron job to run backup.sh daily
  - Verify backup integrity (test restore)
  - Monitor backup frequency and size

**No data validation on input:**
- Problem: User input goes straight to LLM extraction and database
- Files: `app/bot/router.py` (lines 49, 64, 124, etc.)
- Impact: LLM hallucination or format errors silently corrupt data (empty titles, invalid dates)
- Blocking: Can't trust task titles or dates are valid
- Recommendations:
  - Add validation: title length, due date format, priority in range
  - Reject invalid input with user-friendly error, don't use fallback

**No undo/edit on saved items:**
- Problem: Once task, reminder, or decision is created, no way to modify without direct DB access
- Files: All data creation in `app/planning/` and `app/memory/`
- Impact: Typos in task titles, wrong due dates, accidental captures are permanent
- Blocking: Affects user experience
- Recommendations:
  - Add edit/update intents
  - Support "delete task X" natural language
  - Store deletion reason (audit trail)

## Dependencies at Risk

**python-telegram-bot v21.3:**
- Risk: Major library that could have backward-incompatible updates
- Files: `requirements.txt`, `app/main.py`, `app/bot/handlers.py`, `app/bot/jobs.py`
- Current usage: ChatHandler, CommandHandler, filters, job queue
- Recommendations:
  - Pin version: already pinned to 21.3, good
  - Monitor for security updates
  - Test major version upgrades in separate branch before deploying

**httpx (HTTP client):**
- Risk: All external requests go through httpx (Ollama, DuckDuckGo search)
- Files: `app/llm/ollama_client.py`, `app/web/search.py`
- Current mitigation: Timeout set to 10s (search) and 90s (LLM)
- Recommendations:
  - Monitor httpx for security issues
  - Consider fallback if httpx drops support for Python 3.x

**aiosqlite:**
- Risk: Async SQLite wrapper; if development stops, may have compatibility issues
- Files: `app/storage/db.py`
- Current mitigation: Minimal usage, mostly straightforward execute/fetchall
- Recommendations:
  - Consider native sqlite3 if async support not needed
  - Plan PostgreSQL migration path if scaling needed

## Error Handling Gaps

**Generic error responses mask underlying issues:**
- Files: `app/bot/handlers.py` (line 43), `app/llm/ollama_client.py` (lines 24-31)
- Problem: User sees "Something went wrong" but actual error could be Ollama offline, invalid query, or database corruption
- Impact: Difficult to troubleshoot in production
- Recommendations:
  - Return specific error types to user: "Ollama offline", "Invalid date format", "Database error"
  - Add error tracking/alerting (e.g., Sentry) to log stack traces
  - Implement structured logging with error codes

**Async task failures in background job are logged but not alerted:**
- Files: `app/bot/jobs.py` (line 38)
- Problem: Reminder send failures logged only; no notification to user that reminder failed
- Impact: Silent failures - user thinks reminder was sent
- Recommendations:
  - Send user a notification if reminder delivery fails
  - Add maximum retry count and notification on final failure
  - Monitor error log for patterns

---

*Concerns audit: 2026-03-27*
