# Extraction Prompts

Used for structured data extraction from natural language user messages.
These prompts are defined as constants in app/llm/prompts.py.

## Task extraction
Extracts: title, due date, priority, project.

## Reminder extraction
Extracts: title, datetime, optional note.
Always resolves relative dates (e.g. "Friday", "tomorrow") to absolute YYYY-MM-DD HH:MM.

## Decision extraction
Extracts: title, context, decision, reason, alternatives, implications.
