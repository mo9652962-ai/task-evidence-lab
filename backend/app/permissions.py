from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


TASK_ROLES = {"owner", "editor", "reviewer", "viewer"}
ROLE_CAPABILITIES = {
    "owner": {"owner", "editor", "reviewer", "viewer"},
    "editor": {"editor", "viewer"},
    "reviewer": {"reviewer", "viewer"},
    "viewer": {"viewer"},
}


def set_task_membership(connection: sqlite3.Connection, *, task_id: int, user_id: int, role: str, added_by: int | None) -> dict:
    if role not in TASK_ROLES:
        raise ValueError("invalid task role")
    timestamp = datetime.now(timezone.utc).isoformat()
    connection.execute(
        """
        INSERT INTO task_memberships(task_id, user_id, role, created_at, updated_at, added_by)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(task_id, user_id) DO UPDATE SET role = excluded.role, updated_at = excluded.updated_at, added_by = excluded.added_by
        """,
        (task_id, user_id, role, timestamp, timestamp, added_by),
    )
    row = connection.execute("SELECT * FROM task_memberships WHERE task_id = ? AND user_id = ?", (task_id, user_id)).fetchone()
    return dict(row)


def task_role(connection: sqlite3.Connection, task_id: int, principal: dict) -> str | None:
    if principal.get("global_role") == "admin":
        return "admin"
    if not principal.get("id"):
        return None
    row = connection.execute("SELECT role FROM task_memberships WHERE task_id = ? AND user_id = ?", (task_id, principal["id"])).fetchone()
    return row["role"] if row else None


def require_task_role(connection: sqlite3.Connection, task_id: int, principal: dict, allowed_roles: set[str]) -> str:
    role = task_role(connection, task_id, principal)
    if role == "admin" or bool(ROLE_CAPABILITIES.get(role, set()).intersection(allowed_roles)):
        return role
    raise PermissionError("task access denied")
