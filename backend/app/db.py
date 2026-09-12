from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .migrations import CURRENT_SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "task_evidence_lab.db"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB)))


class ClosingConnection(sqlite3.Connection):
    """Make the existing ``with connect()`` pattern release Windows file locks."""

    def __exit__(self, exc_type, exc_value, traceback):
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return result


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft', priority TEXT NOT NULL DEFAULT 'medium', due_at TEXT,
  completion_basis TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived_at TEXT
);
CREATE TABLE IF NOT EXISTS task_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT 'medium',
  completion_basis TEXT NOT NULL DEFAULT '',
  criteria_json TEXT NOT NULL DEFAULT '[]',
  evidence_types_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS acceptance_criteria (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  title TEXT NOT NULL, required INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'pending', note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  title TEXT NOT NULL, evidence_type TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', file_path TEXT,
  external_url TEXT, source TEXT NOT NULL DEFAULT 'manual', verification_status TEXT NOT NULL DEFAULT 'unreviewed',
  review_note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, local_path TEXT, size_bytes INTEGER, sha256 TEXT,
  link_check_status TEXT, link_checked_at TEXT, link_status_code INTEGER, link_final_url TEXT, link_error TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  executor TEXT NOT NULL DEFAULT 'manual', model TEXT, started_at TEXT, finished_at TEXT, status TEXT NOT NULL DEFAULT 'imported',
  raw_source TEXT NOT NULL, source_hash TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(task_id, source_hash)
);
CREATE TABLE IF NOT EXISTS run_steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  step_index INTEGER NOT NULL, step_type TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'unknown'
);
CREATE TABLE IF NOT EXISTS tool_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  step_index INTEGER, tool_name TEXT NOT NULL, input_json TEXT NOT NULL DEFAULT '{}', output_summary TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'unknown', duration_ms INTEGER, risk_level TEXT NOT NULL DEFAULT 'none'
);
CREATE TABLE IF NOT EXISTS changed_files (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  path TEXT NOT NULL, change_type TEXT NOT NULL DEFAULT 'modified', additions INTEGER NOT NULL DEFAULT 0, deletions INTEGER NOT NULL DEFAULT 0,
  risk_level TEXT NOT NULL DEFAULT 'none'
);
CREATE TABLE IF NOT EXISTS test_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'unknown', duration_ms INTEGER, output_summary TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS evaluations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  completion_score INTEGER NOT NULL, evidence_score INTEGER NOT NULL, verification_score INTEGER NOT NULL,
  execution_score INTEGER NOT NULL, risk_score INTEGER NOT NULL, overall_score INTEGER NOT NULL,
  verified INTEGER NOT NULL DEFAULT 0, human_confirmed INTEGER NOT NULL DEFAULT 0, summary TEXT NOT NULL, basis_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  content TEXT NOT NULL, reviewer TEXT NOT NULL DEFAULT 'manual', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
  title TEXT NOT NULL, content TEXT NOT NULL, source_evidence TEXT NOT NULL DEFAULT '', target_type TEXT NOT NULL DEFAULT 'manual',
  status TEXT NOT NULL DEFAULT 'pending', reviewer_note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id INTEGER,
  detail_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_criteria_task ON acceptance_criteria(task_id);
CREATE INDEX IF NOT EXISTS idx_templates_updated ON task_templates(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_task ON evidence(task_id);
CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_task ON evaluations(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_task ON audit_log(task_id, id DESC);
CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(title, description, content='tasks', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS tasks_ai AFTER INSERT ON tasks BEGIN
  INSERT INTO tasks_fts(rowid, title, description) VALUES (new.id, new.title, new.description);
END;
CREATE TRIGGER IF NOT EXISTS tasks_ad AFTER DELETE ON tasks BEGIN
  INSERT INTO tasks_fts(tasks_fts, rowid, title, description) VALUES ('delete', old.id, old.title, old.description);
END;
CREATE TRIGGER IF NOT EXISTS tasks_au AFTER UPDATE OF title, description ON tasks BEGIN
  INSERT INTO tasks_fts(tasks_fts, rowid, title, description) VALUES ('delete', old.id, old.title, old.description);
  INSERT INTO tasks_fts(rowid, title, description) VALUES (new.id, new.title, new.description);
END;
"""


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=5.0, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA cache_size = -20000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            """
            INSERT INTO tasks_fts(rowid, title, description)
            SELECT tasks.id, tasks.title, tasks.description
            FROM tasks
            WHERE tasks.id NOT IN (SELECT rowid FROM tasks_fts)
            """
        )
        evidence_columns = {row["name"] for row in connection.execute("PRAGMA table_info(evidence)")}
        for name, definition in (("local_path", "TEXT"), ("size_bytes", "INTEGER"), ("sha256", "TEXT"), ("link_check_status", "TEXT"), ("link_checked_at", "TEXT"), ("link_status_code", "INTEGER"), ("link_final_url", "TEXT"), ("link_error", "TEXT")):
            if name not in evidence_columns:
                connection.execute(f"ALTER TABLE evidence ADD COLUMN {name} {definition}")
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")


def row_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None
