from __future__ import annotations

import json
import sqlite3
import gzip
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


def _canonical(*, task_id, action, entity_type, entity_id, detail_json, created_at, actor_user_id, request_id, previous_hash) -> str:
    return json.dumps({
        "task_id": task_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "detail_json": detail_json,
        "created_at": created_at,
        "actor_user_id": actor_user_id,
        "request_id": request_id,
        "previous_hash": previous_hash,
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def record_audit(
    connection: sqlite3.Connection,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    task_id: int | None = None,
    detail: dict[str, Any] | None = None,
    created_at: str | None = None,
    actor_user_id: int | None = None,
    request_id: str | None = None,
) -> None:
    if actor_user_id is None:
        from ..auth import current_principal

        principal = current_principal()
        actor_user_id = principal.get("id") or None
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    detail_json = json.dumps(detail or {}, ensure_ascii=False, default=str)
    previous = connection.execute("SELECT event_hash FROM audit_log WHERE event_hash IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
    previous_hash = previous["event_hash"] if previous else None
    event_hash = hashlib.sha256(_canonical(task_id=task_id, action=action, entity_type=entity_type, entity_id=entity_id, detail_json=detail_json, created_at=timestamp, actor_user_id=actor_user_id, request_id=request_id, previous_hash=previous_hash).encode("utf-8")).hexdigest()
    connection.execute(
        "INSERT INTO audit_log(task_id, action, entity_type, entity_id, detail_json, created_at, actor_user_id, request_id, previous_hash, event_hash, redaction_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'v1')",
        (
            task_id,
            action,
            entity_type,
            entity_id,
            detail_json,
            timestamp,
            actor_user_id,
            request_id,
            previous_hash,
            event_hash,
        ),
    )


def verify_audit_chain(connection: sqlite3.Connection) -> bool:
    previous_hash = None
    for row in connection.execute("SELECT * FROM audit_log WHERE event_hash IS NOT NULL ORDER BY id"):
        expected = hashlib.sha256(_canonical(task_id=row["task_id"], action=row["action"], entity_type=row["entity_type"], entity_id=row["entity_id"], detail_json=row["detail_json"], created_at=row["created_at"], actor_user_id=row["actor_user_id"], request_id=row["request_id"], previous_hash=row["previous_hash"]).encode("utf-8")).hexdigest()
        if row["previous_hash"] != previous_hash or row["event_hash"] != expected:
            return False
        previous_hash = row["event_hash"]
    return True


def archive_audit(connection: sqlite3.Connection, destination: str | Path) -> dict:
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    rows = connection.execute("SELECT * FROM audit_log WHERE event_hash IS NOT NULL AND archived_at IS NULL ORDER BY id").fetchall()
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_name = f"audit-{batch_id}.ndjson.gz"
    manifest_name = f"audit-{batch_id}.manifest.json"
    archive_path = target / archive_name
    with gzip.open(archive_path, "wt", encoding="utf-8") as handle:
        for row in rows:
            item = dict(row)
            item["detail"] = json.loads(item.pop("detail_json") or "{}")
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    manifest = {"archive_name": archive_name, "event_count": len(rows), "sha256": digest, "archive_batch_id": batch_id}
    (target / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    timestamp = datetime.now(timezone.utc).isoformat()
    connection.executemany("UPDATE audit_log SET archived_at = ?, archive_batch_id = ? WHERE id = ?", [(timestamp, batch_id, row["id"]) for row in rows])
    return {**manifest, "manifest_name": manifest_name}


def audit_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["detail"] = json.loads(item.pop("detail_json") or "{}")
    return item
