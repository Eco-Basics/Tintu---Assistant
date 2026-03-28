SCHEMA = """
CREATE TABLE IF NOT EXISTS preferences (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT UNIQUE NOT NULL,
    value       TEXT NOT NULL,
    source      TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    status      TEXT DEFAULT 'active',
    phase       TEXT,
    summary     TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id       INTEGER REFERENCES projects(id),
    title            TEXT NOT NULL,
    description      TEXT,
    status           TEXT DEFAULT 'inbox',
    priority         INTEGER DEFAULT 0,
    due_date         TEXT,
    recurrence_rule  TEXT,
    source_note      TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    completed_at     TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER REFERENCES tasks(id),
    title       TEXT NOT NULL,
    message     TEXT,
    remind_at   TEXT NOT NULL,
    status      TEXT DEFAULT 'pending',
    created_at  TEXT DEFAULT (datetime('now')),
    sent_at     TEXT
);

CREATE TABLE IF NOT EXISTS routines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    description     TEXT,
    schedule_type   TEXT NOT NULL,
    schedule_value  TEXT NOT NULL,
    is_active       INTEGER DEFAULT 1,
    last_run_at     TEXT,
    next_run_at     TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT,
    starts_at   TEXT NOT NULL,
    ends_at     TEXT,
    location    TEXT,
    project_id  INTEGER REFERENCES projects(id),
    status      TEXT DEFAULT 'upcoming',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversation_summaries (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    date                 TEXT NOT NULL,
    summary              TEXT NOT NULL,
    topics               TEXT,
    projects             TEXT,
    actions              TEXT,
    decisions            TEXT,
    source_message_range TEXT,
    created_at           TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decision_index (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    decision_date TEXT NOT NULL,
    project_id    INTEGER REFERENCES projects(id),
    markdown_path TEXT NOT NULL,
    summary       TEXT,
    tags          TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS message_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_message_id INTEGER,
    direction           TEXT NOT NULL,
    kind                TEXT NOT NULL,
    summary             TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS personality_traits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    confidence  REAL DEFAULT 1.0,
    source      TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS personas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    is_active   INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""
