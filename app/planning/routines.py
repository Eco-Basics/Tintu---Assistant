from app.storage.db import execute, fetchall, fetchone


async def create_routine(
    name: str,
    description: str,
    schedule_type: str,
    schedule_value: str,
) -> int:
    return await execute(
        """INSERT INTO routines (name, description, schedule_type, schedule_value)
           VALUES (?, ?, ?, ?)""",
        (name, description, schedule_type, schedule_value),
    )


async def list_routines(active_only: bool = True) -> list[dict]:
    if active_only:
        return await fetchall("SELECT * FROM routines WHERE is_active = 1 ORDER BY id")
    return await fetchall("SELECT * FROM routines ORDER BY id")


async def toggle_routine(routine_id: int, active: bool) -> bool:
    r = await fetchone("SELECT id FROM routines WHERE id = ?", (routine_id,))
    if not r:
        return False
    await execute(
        "UPDATE routines SET is_active = ? WHERE id = ?",
        (1 if active else 0, routine_id),
    )
    return True
