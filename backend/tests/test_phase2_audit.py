from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.db import connect
from app.main import app
from app.services.audit import archive_audit, record_audit, verify_audit_chain


def test_audit_events_form_a_verifiable_hash_chain() -> None:
    with TestClient(app):
        with connect() as connection:
            connection.execute("DELETE FROM audit_log")
            record_audit(connection, action="test.one", entity_type="test", detail={"safe": True}, request_id="req-1")
            record_audit(connection, action="test.two", entity_type="test", detail={"safe": True}, request_id="req-2")
            assert verify_audit_chain(connection) is True
            connection.execute("UPDATE audit_log SET detail_json = ? WHERE action = 'test.one'", (json.dumps({"safe": False}),))
            assert verify_audit_chain(connection) is False


def test_audit_archive_writes_ndjson_and_manifest(tmp_path) -> None:
    with TestClient(app):
        with connect() as connection:
            record_audit(connection, action="test.archive", entity_type="test", detail={"value": "redacted"})
            result = archive_audit(connection, tmp_path)

    assert result["event_count"] >= 1
    assert (tmp_path / result["archive_name"]).is_file()
    assert (tmp_path / result["manifest_name"]).is_file()
