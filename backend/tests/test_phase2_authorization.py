from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app import main
from app.auth import upsert_oidc_user
from app.db import connect
from app.permissions import require_task_role, set_task_membership
from app.settings import AppSettings


def test_task_membership_enforces_role_order() -> None:
    with TestClient(main.app):
        with connect() as connection:
            owner = upsert_oidc_user(connection, issuer="https://issuer", subject="owner", email=None, display_name=None, groups=[], admin_groups=set())
            editor = upsert_oidc_user(connection, issuer="https://issuer", subject="editor", email=None, display_name=None, groups=[], admin_groups=set())
            task = connection.execute("INSERT INTO tasks(title, created_at, updated_at) VALUES ('权限任务', '2026-01-01', '2026-01-01')").lastrowid
            set_task_membership(connection, task_id=task, user_id=owner["id"], role="owner", added_by=owner["id"])
            set_task_membership(connection, task_id=task, user_id=editor["id"], role="editor", added_by=owner["id"])
            require_task_role(connection, task, editor, {"viewer"})
            try:
                require_task_role(connection, task, editor, {"owner"})
            except PermissionError:
                pass
            else:
                raise AssertionError("editor must not satisfy owner-only access")


def test_production_accepts_only_trusted_proxy_identity(monkeypatch) -> None:
    monkeypatch.setenv("TASK_EVIDENCE_DEPLOYMENT_PROFILE", "production")
    monkeypatch.setenv("TASK_EVIDENCE_PUBLIC_BASE_URL", "https://evidence.example.com")
    monkeypatch.setenv("TASK_EVIDENCE_ALLOWED_HOSTS", "testserver")
    monkeypatch.setenv("TASK_EVIDENCE_TRUSTED_PROXY_IPS", "127.0.0.1")
    monkeypatch.setenv("TASK_EVIDENCE_OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setenv("TASK_EVIDENCE_OIDC_ADMIN_GROUPS", "admins")
    monkeypatch.setenv("TASK_EVIDENCE_REDIS_REQUIRED", "false")
    monkeypatch.setattr(main, "settings", AppSettings.from_env())

    with TestClient(main.app, base_url="https://testserver", client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/tasks").status_code == 401
        response = client.get(
            "/api/tasks",
            headers={
                "X-Auth-Request-User": "stable-subject",
                "X-Auth-Request-Email": "person@example.com",
                "X-Auth-Request-Groups": "admins",
            },
        )
        assert response.status_code == 200
        assert "__Host-task_evidence_session=" in response.headers["set-cookie"]
        assert client.get("/api/auth/me").json()["global_role"] == "admin"
