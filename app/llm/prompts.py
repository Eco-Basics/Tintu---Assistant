SYSTEM_PROMPT = """\
You are a private planning and memory assistant. You help with:
- planning, scheduling, and reminders
- task and project tracking
- note capture and decision logging
- daily summaries and reviews
- retrieving prior notes and conversation context

Tone: concise, structured, thoughtful. Not chatty.
- Answer directly. Use headings and bullets when useful.
- Ask follow-up questions only when needed to avoid ambiguity.
- Do not over-explain simple actions.
- Distinguish clearly between facts, assumptions, and retrieved memory.
- Do not answer questions outside your role unless explicitly asked.\
"""

CLASSIFICATION_PROMPT = """\
Classify the following user message into exactly one of these types:
answer, capture_note, create_task, set_reminder, create_routine,
project_update, retrieval_query, compare_context, draft_reply,
daily_summary, end_of_day_review, update_preference,
list_tasks, complete_task, list_reminders, search

Message: {message}

Reply with only the type, nothing else.\
"""

TASK_EXTRACT_PROMPT = """\
Extract a task from the following message.

Message: {message}

Respond in this exact format (leave a field empty if not mentioned):
Title: <task title>
Due: <YYYY-MM-DD or empty>
Priority: <high/normal/low>
Project: <project name or empty>\
"""

REMINDER_EXTRACT_PROMPT = """\
Extract reminder details. Today is {today}. Resolve relative dates (tomorrow, Friday, next week) to absolute dates.

Message: {message}

Respond in this exact format:
Title: <what to remind about>
When: <YYYY-MM-DD HH:MM>
Note: <optional extra note or empty>\
"""

DECISION_EXTRACT_PROMPT = """\
Extract a structured decision log from the following message.

Message: {message}

Respond in this exact format:
Title: <decision title>
Context: <brief context>
Decision: <what was decided>
Reason: <why>
Alternatives: <alternatives considered or none>
Implications: <implications or none>\
"""

COMPLETE_TASK_EXTRACT_PROMPT = """\
The user says they completed a task. Extract which task they mean.

Message: {message}

Open tasks:
{task_list}

Reply with only the task ID number that best matches. If unclear, reply with 0.\
"""

PREFERENCE_EXTRACT_PROMPT = """\
Extract a user preference from the following message.

Message: {message}

Respond in this exact format:
Key: <short snake_case key, e.g. morning_summary_time, default_project, timezone>
Value: <the preference value>
Source: <natural language description of what was said>\
"""

DAILY_SUMMARY_PROMPT = """\
Generate a daily summary for {date}.

Tasks created today: {tasks_created}
Tasks completed today: {tasks_completed}
Reminders set: {reminders}
Decisions logged: {decisions}

Write a clean, structured daily summary with sections:
- Summary
- Completed
- Open tasks
- Reminders set
- Decisions
- Open loops\
"""

EOD_REVIEW_PROMPT = """\
Generate an end-of-day review for {date}.

Completed tasks: {completed}
Still open tasks: {open_tasks}
Upcoming deadlines: {deadlines}
Decisions today: {decisions}

Write a clean end-of-day review with sections:
- Completed today
- Still open
- What changed
- Upcoming deadlines
- Suggested first steps for tomorrow\
"""
