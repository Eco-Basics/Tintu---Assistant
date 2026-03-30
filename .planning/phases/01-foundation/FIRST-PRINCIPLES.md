╔══════════════════════════════════════════════════════════════╗
║  FIRST PRINCIPLES BRIEF                                      ║
╚══════════════════════════════════════════════════════════════╝

THE CORE IDEA (plain language):
Tintu is a personal assistant running on a small AI model (Qwen3:4b) that lives
on your own server. Small models are great at remembering your habits and talking
with you naturally — but they confidently make up code, math, and external facts.
Phase 1 makes Tintu honest: it stops before answering when the question is
outside what it can do reliably, and it lays down the database tables that will
hold everything it learns about you.

EXAMPLE 1: You message Tintu "write me a Python function to parse JSON".
Without Phase 1, Tintu invents a function that looks right but has subtle bugs —
and presents it confidently. With Phase 1, Tintu immediately replies "I can't
write or debug code — that's outside what I can do reliably." No Ollama call is
ever made. No wrong output reaches you.

EXAMPLE 2: You message Tintu "remind me to review the deploy at 5pm". This
classifies as a reminder — not a code/math/research request — so it passes
straight through the refusal guard to the reminder handler. Phase 1 never blocks
the things Tintu is actually good at.

CORE ASPECTS COVERED:
  • Capability refusal guard: Pre-generation keyword check in route() — if intent
    is "answer" and the message asks for code, math, or research, route() returns
    a one-sentence honest refusal before calling Ollama. The user never receives a
    hallucinated answer.
  • Intent bypass: Task, reminder, and retrieval intents skip the refusal check
    entirely — only the general-answer path is guarded.
  • DB schema for personality: Two new SQLite tables (personality_traits, personas)
    are added with additive CREATE TABLE IF NOT EXISTS migrations. No existing
    rows are touched. These tables are empty after Phase 1 — Phase 2 will write to
    them.
  • Test foundation: pytest infrastructure created from scratch (Wave 0), giving
    the project its first automated test suite. 9 tests covering refusal behavior
    and schema migration.

LOAD-BEARING TRUTHS (what the entire project rests on):
  • Confident wrong answers destroy trust; a clear refusal is recoverable
  • If no Ollama call is made, no hallucinated content can reach the user
  • Qwen3:4b has documented capability gaps on code, math, and external knowledge
  • Both bots share one codebase — one change protects both
  • Personality features have negative value until wrong answers are stopped

ASSUMPTIONS STILL IN PLAY (watch these — if wrong, re-plan):
  • [LOAD-BEARING] The keyword/intent classifier reliably separates "answer"
    intents from task/reminder intents — false negatives let hallucinations through
  • [CONDITIONAL] The preferences table schema is compatible with Phase 2's
    PromptBuilder needs — if not, a schema migration will be needed in Phase 2
  • [CONDITIONAL] The refusal category list (code, math, research) is complete
    enough — edge cases will exist but common-case coverage is the goal
