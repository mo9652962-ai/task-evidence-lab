from __future__ import annotations

import argparse
import json
import sqlite3


CURRENT_SCHEMA_VERSION = 4


def schema_status(connection: sqlite3.Connection) -> dict:
    current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    return {
        "current_version": current_version,
        "latest_version": CURRENT_SCHEMA_VERSION,
        "ready": current_version == CURRENT_SCHEMA_VERSION,
    }


def _run_command(command: str) -> dict:
    from .db import connect, init_db

    if command == "upgrade":
        init_db()
    with connect() as connection:
        return schema_status(connection)


def main() -> None:
    parser = argparse.ArgumentParser(description="Task Evidence Lab SQLite schema management")
    parser.add_argument("command", choices=("status", "upgrade"))
    args = parser.parse_args()
    result = _run_command(args.command)
    print(json.dumps(result, ensure_ascii=False))
    if args.command == "status" and not result["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
