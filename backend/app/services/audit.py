from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def record_audit(
    connection: sqlite3.Connection,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    task_id: int | None = None,
    detail: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> None:
    connection.execute(
        "INSERT INTO audit_log(task_id, action, entity_type, entity_id, detail_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            task_id,
            action,
            entity_type,
            entity_id,
            json.dumps(detail or {}, ensure_ascii=False, default=str),
            created_at or datetime.now(timezone.utc).isoformat(),
        ),
    )


def audit_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["detail"] = json.loads(item.pop("detail_json") or "{}")
    return item
