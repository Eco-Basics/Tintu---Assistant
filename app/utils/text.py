def truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def fmt_task_line(task: dict) -> str:
    icons = {
        "inbox": "📥",
        "next": "▶️",
        "active": "🔄",
        "waiting": "⏳",
        "done": "✅",
        "cancelled": "❌",
    }
    icon = icons.get(task["status"], "•")
    due = f" — due {task['due_date']}" if task.get("due_date") else ""
    proj = f" [{task['project_name']}]" if task.get("project_name") else ""
    return f"{icon} `{task['id']}` {task['title']}{proj}{due}"


def fmt_reminder_line(r: dict) -> str:
    return f"⏰ `{r['id']}` {r['title']} — {r['remind_at']}"


def fmt_routine_line(r: dict) -> str:
    active = "✅" if r["is_active"] else "⏸"
    return f"{active} `{r['id']}` {r['name']} ({r['schedule_type']}: {r['schedule_value']})"
