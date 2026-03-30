from app.storage.db import fetchall
from app.memory.vault import search_vault


async def retrieve_context(query: str) -> str:
    parts = []

    tasks = await fetchall(
        "SELECT title, status, due_date FROM tasks WHERE title LIKE ? LIMIT 5",
        (f"%{query}%",),
    )
    if tasks:
        lines = "\n".join(
            f"- [{t['status']}] {t['title']}" + (f" (due {t['due_date']})" if t.get("due_date") else "")
            for t in tasks
        )
        parts.append(f"Tasks:\n{lines}")

    decisions = await fetchall(
        "SELECT title, decision_date, summary FROM decision_index "
        "WHERE title LIKE ? OR summary LIKE ? ORDER BY decision_date DESC LIMIT 3",
        (f"%{query}%", f"%{query}%"),
    )
    if decisions:
        lines = "\n".join(f"- {d['decision_date']}: {d['title']}" for d in decisions)
        parts.append(f"Decisions:\n{lines}")

    summaries = await fetchall(
        "SELECT date, summary FROM conversation_summaries "
        "WHERE summary LIKE ? ORDER BY date DESC LIMIT 3",
        (f"%{query}%",),
    )
    if summaries:
        lines = "\n".join(f"- {s['date']}: {s['summary'][:120]}" for s in summaries)
        parts.append(f"Conversation history:\n{lines}")

    vault_hits = search_vault(query, max_results=5)
    if vault_hits:
        lines = "\n".join(f"- {h['path']}: {h['snippet']}" for h in vault_hits)
        parts.append(f"Notes:\n{lines}")

    return "\n\n".join(parts) if parts else ""
