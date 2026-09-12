from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.security import add_security_headers, session_cookie_options
from app.settings import AppSettings
from app.main import app


def test_production_profile_requires_public_url_and_explicit_hosts(monkeypatch) -> None:
    monkeypatch.setenv("TASK_EVIDENCE_DEPLOYMENT_PROFILE", "production")
    monkeypatch.delenv("TASK_EVIDENCE_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("TASK_EVIDENCE_ALLOWED_HOSTS", raising=False)

    with pytest.raises(ValueError, match="PUBLIC_BASE_URL"):
        AppSettings.from_env()


def test_production_profile_enables_secure_cookie_policy(monkeypatch) -> None:
    monkeypatch.setenv("TASK_EVIDENCE_DEPLOYMENT_PROFILE", "production")
    monkeypatch.setenv("TASK_EVIDENCE_PUBLIC_BASE_URL", "https://evidence.example.com")
    monkeypatch.setenv("TASK_EVIDENCE_ALLOWED_HOSTS", "evidence.example.com")
    monkeypatch.setenv("TASK_EVIDENCE_TRUSTED_PROXY_IPS", "127.0.0.1,10.0.0.0/8")

    settings = AppSettings.from_env()

    assert settings.secure_headers is True
    assert settings.allowed_hosts == ["evidence.example.com"]
    assert settings.is_trusted_proxy("10.10.10.4") is True
    assert settings.is_trusted_proxy("192.168.1.4") is False
    assert session_cookie_options(settings) == {"httponly": True, "secure": True, "samesite": "lax", "path": "/"}


def test_security_headers_add_hsts_only_for_https() -> None:
    from starlette.responses import Response

    http_response = add_security_headers(Response(), secure_transport=False, enable_hsts=True)
    https_response = add_security_headers(Response(), secure_transport=True, enable_hsts=True)

    assert "strict-transport-security" not in http_response.headers
    assert https_response.headers["strict-transport-security"].startswith("max-age=")
    assert https_response.headers["x-content-type-options"] == "nosniff"


def test_untrusted_host_is_rejected() -> None:
    with TestClient(app) as client:
        assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400
        assert client.get("/api/health", headers={"host": "testserver"}).status_code == 200
