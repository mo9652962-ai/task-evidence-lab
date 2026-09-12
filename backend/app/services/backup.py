from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


BACKUP_SCHEMA_VERSION = 1
BACKUP_TABLES = (
    "tasks",
    "task_templates",
    "acceptance_criteria",
    "evidence",
    "runs",
    "run_steps",
    "tool_calls",
    "changed_files",
    "test_results",
    "evaluations",
    "reviews",
    "memory_candidates",
    "audit_log",
)


class BackupError(ValueError):
    pass


def export_backup(connection: sqlite3.Connection) -> dict:
    tables = {
        table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
        for table in BACKUP_TABLES
    }
    return {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
    }


def restore_backup(connection: sqlite3.Connection, backup: dict) -> None:
    if not isinstance(backup, dict) or backup.get("schema_version") != BACKUP_SCHEMA_VERSION:
        raise BackupError("不支持的备份版本")
    tables = backup.get("tables")
    if not isinstance(tables, dict):
        raise BackupError("备份缺少 tables 对象")

    table_columns: dict[str, set[str]] = {}
    for table in BACKUP_TABLES:
        table_columns[table] = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        records = tables.get(table, [])
        if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
            raise BackupError(f"备份表 {table} 必须是对象数组")
        unknown = {key for record in records for key in record if key not in table_columns[table]}
        if unknown:
            raise BackupError(f"备份表 {table} 含未知字段：{', '.join(sorted(unknown))}")

    for table in reversed(BACKUP_TABLES):
        connection.execute(f"DELETE FROM {table}")
    for table in BACKUP_TABLES:
        for record in tables.get(table, []):
            columns = [column for column in record if column in table_columns[table]]
            if not columns:
                raise BackupError(f"备份表 {table} 存在空记录")
            placeholders = ", ".join("?" for _ in columns)
            names = ", ".join(columns)
            connection.execute(
                f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
                [record[column] for column in columns],
            )
