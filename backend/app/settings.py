from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlparse


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppSettings:
    profile: str
    public_base_url: str | None
    allowed_hosts: list[str]
    trusted_proxy_ips: list[str]
    secure_headers: bool
    session_cookie_name: str
    session_cookie_secure: bool
    session_cookie_samesite: str
    oidc_issuer: str | None
    oidc_subject_header: str
    oidc_email_header: str
    oidc_groups_header: str
    oidc_admin_groups: set[str]
    session_absolute_seconds: int
    session_idle_seconds: int
    redis_url: str | None
    redis_required: bool
    redis_prefix: str

    @classmethod
    def from_env(cls) -> "AppSettings":
        profile = os.getenv("TASK_EVIDENCE_DEPLOYMENT_PROFILE", "local").strip().lower() or "local"
        if profile not in {"local", "production"}:
            raise ValueError("TASK_EVIDENCE_DEPLOYMENT_PROFILE must be local or production")
        raw_public_url = os.getenv("TASK_EVIDENCE_PUBLIC_BASE_URL", "").strip()
        public_base_url = raw_public_url or None
        raw_hosts = os.getenv("TASK_EVIDENCE_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        allowed_hosts = _split(raw_hosts)
        raw_proxies = os.getenv("TASK_EVIDENCE_TRUSTED_PROXY_IPS", "127.0.0.1")
        trusted_proxy_ips = _split(raw_proxies)
        if profile == "production":
            if not public_base_url or urlparse(public_base_url).scheme != "https":
                raise ValueError("production profile requires TASK_EVIDENCE_PUBLIC_BASE_URL with https://")
            if not os.getenv("TASK_EVIDENCE_ALLOWED_HOSTS", "").strip() or not allowed_hosts or "*" in allowed_hosts:
                raise ValueError("production profile requires explicit TASK_EVIDENCE_ALLOWED_HOSTS")
            if not os.getenv("TASK_EVIDENCE_TRUSTED_PROXY_IPS", "").strip() or not trusted_proxy_ips:
                raise ValueError("production profile requires explicit TASK_EVIDENCE_TRUSTED_PROXY_IPS")
        cookie_samesite = os.getenv("TASK_EVIDENCE_SESSION_COOKIE_SAMESITE", "lax").strip().lower()
        if cookie_samesite not in {"lax", "strict", "none"}:
            raise ValueError("TASK_EVIDENCE_SESSION_COOKIE_SAMESITE must be lax, strict, or none")
        cookie_secure = _as_bool(os.getenv("TASK_EVIDENCE_SESSION_COOKIE_SECURE"), default=profile == "production")
        if cookie_samesite == "none" and not cookie_secure:
            raise ValueError("SameSite=None requires a secure session cookie")
        cookie_name = os.getenv("TASK_EVIDENCE_SESSION_COOKIE_NAME", "").strip()
        if not cookie_name:
            cookie_name = "__Host-task_evidence_session" if profile == "production" else "task_evidence_session"
        absolute_seconds = int(os.getenv("TASK_EVIDENCE_SESSION_ABSOLUTE_SECONDS", str(8 * 60 * 60)))
        idle_seconds = int(os.getenv("TASK_EVIDENCE_SESSION_IDLE_SECONDS", str(30 * 60)))
        if absolute_seconds < 300 or idle_seconds < 60 or idle_seconds > absolute_seconds:
            raise ValueError("session timeout values are invalid")
        return cls(
            profile=profile,
            public_base_url=public_base_url,
            allowed_hosts=allowed_hosts,
            trusted_proxy_ips=trusted_proxy_ips,
            secure_headers=_as_bool(os.getenv("TASK_EVIDENCE_SECURE_HEADERS"), default=profile == "production"),
            session_cookie_name=cookie_name,
            session_cookie_secure=cookie_secure,
            session_cookie_samesite=cookie_samesite,
            oidc_issuer=os.getenv("TASK_EVIDENCE_OIDC_ISSUER", "").strip() or None,
            oidc_subject_header=os.getenv("TASK_EVIDENCE_OIDC_SUBJECT_HEADER", "X-Auth-Request-User").strip(),
            oidc_email_header=os.getenv("TASK_EVIDENCE_OIDC_EMAIL_HEADER", "X-Auth-Request-Email").strip(),
            oidc_groups_header=os.getenv("TASK_EVIDENCE_OIDC_GROUPS_HEADER", "X-Auth-Request-Groups").strip(),
            oidc_admin_groups=set(_split(os.getenv("TASK_EVIDENCE_OIDC_ADMIN_GROUPS", ""))),
            session_absolute_seconds=absolute_seconds,
            session_idle_seconds=idle_seconds,
            redis_url=os.getenv("TASK_EVIDENCE_REDIS_URL", "").strip() or None,
            redis_required=_as_bool(os.getenv("TASK_EVIDENCE_REDIS_REQUIRED"), default=profile == "production"),
            redis_prefix=os.getenv("TASK_EVIDENCE_RATE_LIMIT_PREFIX", "task-evidence-lab").strip() or "task-evidence-lab",
        )

    def is_trusted_proxy(self, address: str | None) -> bool:
        if not address:
            return False
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            return False
        for value in self.trusted_proxy_ips:
            try:
                if parsed in ipaddress.ip_network(value, strict=False):
                    return True
            except ValueError:
                if address == value:
                    return True
        return False
