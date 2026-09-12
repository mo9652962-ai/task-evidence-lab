from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.auth import create_session, revoke_session, resolve_session, upsert_oidc_user
from app.db import connect
from app.main import app


def test_oidc_identity_is_keyed_by_issuer_and_stable_subject() -> None:
    with TestClient(app):
        with connect() as connection:
            first = upsert_oidc_user(
                connection,
                issuer="https://issuer.example",
                subject="stable-subject",
                email="old@example.com",
                display_name="Old Name",
                groups=["evidence-admin"],
                admin_groups={"evidence-admin"},
            )
            second = upsert_oidc_user(
                connection,
                issuer="https://issuer.example",
                subject="stable-subject",
                email="new@example.com",
                display_name="New Name",
                groups=[],
                admin_groups={"evidence-admin"},
            )

    assert first["id"] == second["id"]
    assert second["email"] == "new@example.com"
    assert second["global_role"] == "member"


def test_session_stores_only_hash_and_can_be_revoked() -> None:
    with TestClient(app):
        with connect() as connection:
            user = upsert_oidc_user(
                connection,
                issuer="https://issuer.example",
                subject="session-user",
                email="session@example.com",
                display_name="Session User",
                groups=[],
                admin_groups=set(),
            )
            token, session = create_session(
                connection,
                user_id=user["id"],
                now=datetime.now(timezone.utc),
                absolute_ttl=timedelta(hours=8),
                idle_ttl=timedelta(minutes=30),
            )
            stored = connection.execute("SELECT * FROM user_sessions WHERE id = ?", (session["id"],)).fetchone()
            assert stored["token_hash"] != token
            assert resolve_session(connection, token, datetime.now(timezone.utc))["user_id"] == user["id"]
            revoke_session(connection, token, reason="logout", now=datetime.now(timezone.utc))
            assert resolve_session(connection, token, datetime.now(timezone.utc)) is None


def test_auth_me_returns_local_compatibility_principal() -> None:
    with TestClient(app) as client:
        response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["global_role"] == "admin"
    assert response.json()["subject"] == "local:default"
