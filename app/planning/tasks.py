from app.storage.db import execute, fetchall, fetchone
from app.utils.time import today_str


async def create_task(
    title: str,
    description: str = "",
    due_date: str = "",
    priority: int = 0,
    project_id: int | None = None,
    source_note: str = "",
) -> int:
    return await execute(
        """INSERT INTO tasks (title, description, due_date, priority, project_id, source_note)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, description, due_date or None, priority, project_id, source_note),
    )


async def list_tasks(
    status: str | None = None,
    project_id: int | None = None,
    due_today: bool = False,
) -> list[dict]:
    where = []
    params: list = []

    if status:
        where.append("t.status = ?")
        params.append(status)
    else:
        where.append("t.status NOT IN ('done', 'cancelled')")

    if project_id:
        where.append("t.project_id = ?")
        params.append(project_id)

    if due_today:
        where.append("t.due_date <= ?")
        params.append(today_str())

    clause = "WHERE " + " AND ".join(where) if where else ""
    query = f"""
        SELECT t.id, t.title, t.status, t.due_date, t.priority,
               p.name AS project_name
        FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
        {clause}
        ORDER BY t.priority DESC, t.due_date ASC, t.id ASC
        LIMIT 50
    """
    return await fetchall(query, tuple(params))


async def complete_task(task_id: int) -> bool:
    task = await fetchone("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if not task:
        return False
    await execute(
        "UPDATE tasks SET status = 'done', completed_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
        (task_id,),
    )
    return True


async def update_task_status(task_id: int, status: str) -> bool:
    task = await fetchone("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if not task:
        return False
    await execute(
        "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, task_id),
    )
    return True
