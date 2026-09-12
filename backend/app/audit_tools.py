from __future__ import annotations

import argparse
import json

from .db import connect, init_db
from .services.audit import archive_audit, verify_audit_chain


def main() -> None:
    parser = argparse.ArgumentParser(description="Task Evidence Lab audit maintenance")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify")
    archive_parser = subparsers.add_parser("archive")
    archive_parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    init_db()
    with connect() as connection:
        if args.command == "verify":
            result = {"valid": verify_audit_chain(connection)}
            print(json.dumps(result, ensure_ascii=False))
            if not result["valid"]:
                raise SystemExit(1)
        else:
            print(json.dumps(archive_audit(connection, args.destination), ensure_ascii=False))


if __name__ == "__main__":
    main()
