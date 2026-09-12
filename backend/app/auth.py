from __future__ import annotations

import hashlib
import secrets
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import sqlite3
from typing import Iterable


AUTH_COOKIE = "__Host-task_evidence_session"
_principal: ContextVar[dict | None] = ContextVar("task_evidence_principal", default=None)


@dataclass(frozen=True)
class SessionPolicy:
    absolute_ttl: timedelta = timedelta(hours=8)
    idle_ttl: timedelta = timedelta(minutes=30)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def upsert_oidc_user(
    connection: sqlite3.Connection,
    *,
    issuer: str,
    subject: str,
    email: str | None,
    display_name: str | None,
    groups: Iterable[str],
    admin_groups: set[str],
    now: datetime | None = None,
) -> dict:
    if not issuer.strip() or not subject.strip():
        raise ValueError("OIDC issuer and subject are required")
    timestamp = _iso(now or utcnow())
    role = "admin" if admin_groups.intersection(set(groups)) else "member"
    connection.execute(
        """
        INSERT INTO users(issuer, subject, email, display_name, status, created_at, updated_at, last_login_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
        ON CONFLICT(issuer, subject) DO UPDATE SET
          email = excluded.email,
          display_name = excluded.display_name,
          updated_at = excluded.updated_at,
          last_login_at = excluded.last_login_at
        """,
        (issuer.strip(), subject.strip(), email, display_name, timestamp, timestamp, timestamp),
    )
    row = connection.execute("SELECT * FROM users WHERE issuer = ? AND subject = ?", (issuer.strip(), subject.strip())).fetchone()
    if not row:
        raise RuntimeError("OIDC user upsert failed")
    connection.execute(
        "INSERT INTO user_global_roles(user_id, role) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET role = excluded.role",
        (row["id"], role),
    )
    result = dict(connection.execute("SELECT users.*, user_global_roles.role AS global_role FROM users JOIN user_global_roles ON user_global_roles.user_id = users.id WHERE users.id = ?", (row["id"],)).fetchone())
    return result


def create_session(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    now: datetime | None = None,
    absolute_ttl: timedelta = SessionPolicy.absolute_ttl,
    idle_ttl: timedelta = SessionPolicy.idle_ttl,
    ip_hash: str | None = None,
    user_agent_hash: str | None = None,
) -> tuple[str, dict]:
    current = now or utcnow()
    token = secrets.token_urlsafe(32)
    created_at = _iso(current)
    expires_at = _iso(current + absolute_ttl)
    connection.execute(
        "INSERT INTO user_sessions(user_id, token_hash, created_at, last_seen_at, expires_at, ip_hash, user_agent_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, token_hash(token), created_at, created_at, expires_at, ip_hash, user_agent_hash),
    )
    row = connection.execute("SELECT * FROM user_sessions WHERE token_hash = ?", (token_hash(token),)).fetchone()
    if not row:
        raise RuntimeError("session creation failed")
    return token, dict(row)


def resolve_session(connection: sqlite3.Connection, token: str | None, now: datetime | None = None, idle_ttl: timedelta = SessionPolicy.idle_ttl) -> dict | None:
    if not token:
        return None
    row = connection.execute(
        "SELECT user_sessions.*, users.issuer, users.subject, users.email, users.display_name, users.status, user_global_roles.role AS global_role FROM user_sessions JOIN users ON users.id = user_sessions.user_id JOIN user_global_roles ON user_global_roles.user_id = users.id WHERE user_sessions.token_hash = ?",
        (token_hash(token),),
    ).fetchone()
    if not row:
        return None
    current = now or utcnow()
    if row["revoked_at"] or row["status"] != "active" or _parse(row["expires_at"]) <= current:
        return None
    if _parse(row["last_seen_at"]) + idle_ttl <= current:
        return None
    connection.execute("UPDATE user_sessions SET last_seen_at = ? WHERE id = ?", (_iso(current), row["id"]))
    return dict(row)


def revoke_session(connection: sqlite3.Connection, token: str, *, reason: str, now: datetime | None = None) -> bool:
    cursor = connection.execute(
        "UPDATE user_sessions SET revoked_at = ?, revoke_reason = ? WHERE token_hash = ? AND revoked_at IS NULL",
        (_iso(now or utcnow()), reason, token_hash(token)),
    )
    return cursor.rowcount > 0


def revoke_user_sessions(connection: sqlite3.Connection, user_id: int, *, reason: str, now: datetime | None = None) -> int:
    cursor = connection.execute(
        "UPDATE user_sessions SET revoked_at = ?, revoke_reason = ? WHERE user_id = ? AND revoked_at IS NULL",
        (_iso(now or utcnow()), reason, user_id),
    )
    return cursor.rowcount


def set_principal(value: dict | None):
    return _principal.set(value)


def reset_principal(token) -> None:
    _principal.reset(token)


def current_principal() -> dict:
    return _principal.get() or {
        "id": 0,
        "issuer": "local",
        "subject": "local:default",
        "email": None,
        "display_name": "Local administrator",
        "status": "active",
        "global_role": "admin",
        "session_id": None,
    }


def authenticate_request(request, connection: sqlite3.Connection, settings) -> tuple[dict | None, str | None]:
    if not settings.is_trusted_proxy(request.client.host if request.client else None):
        return None, None
    subject = request.headers.get(settings.oidc_subject_header, "").strip()
    issuer = request.headers.get("X-Auth-Request-Issuer", "").strip() or settings.oidc_issuer
    email = request.headers.get(settings.oidc_email_header, "").strip() or None
    group_header = request.headers.get(settings.oidc_groups_header, "")
    groups = {item.strip() for item in group_header.replace(",", " ").split() if item.strip()}
    cookie_token = request.cookies.get(settings.session_cookie_name)
    if cookie_token:
        session = resolve_session(connection, cookie_token, idle_ttl=timedelta(seconds=settings.session_idle_seconds))
        if not session:
            return None, None
        if subject and issuer and (session["subject"] != subject or session["issuer"] != issuer):
            return None, None
        return session, None
    if not subject or not issuer:
        return None, None
    user = upsert_oidc_user(
        connection,
        issuer=issuer,
        subject=subject,
        email=email,
        display_name=email,
        groups=groups,
        admin_groups=settings.oidc_admin_groups,
    )
    token, session = create_session(
        connection,
        user_id=user["id"],
        absolute_ttl=timedelta(seconds=settings.session_absolute_seconds),
        idle_ttl=timedelta(seconds=settings.session_idle_seconds),
    )
    user["session_id"] = session["id"]
    return user, token
