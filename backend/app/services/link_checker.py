from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse


class LinkCheckError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, msg, headers, new_url):
        return None


def _public_addresses(hostname: str, port: int) -> list[str]:
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise LinkCheckError(f"无法解析链接主机：{hostname}") from exc
    addresses = sorted({record[4][0] for record in records})
    if not addresses:
        raise LinkCheckError(f"无法解析链接主机：{hostname}")
    for raw_address in addresses:
        address = ipaddress.ip_address(raw_address)
        if not address.is_global:
            raise LinkCheckError("链接目标解析到本机或内网地址，已拒绝检查")
    return addresses


def check_external_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise LinkCheckError("只允许检查 http 或 https 链接")
    if not parsed.hostname:
        raise LinkCheckError("链接缺少主机名")
    if parsed.username or parsed.password:
        raise LinkCheckError("链接不允许携带用户名或密码")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise LinkCheckError("链接端口无效") from exc
    if port not in (80, 443):
        raise LinkCheckError("只允许检查 80 或 443 端口")
    _public_addresses(parsed.hostname, port)

    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "TaskEvidenceLab-LinkChecker/1.0"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=5) as response:
            status_code = response.getcode()
            final_url = response.geturl()
            return {"reachable": 200 <= status_code < 400, "status": "reachable" if status_code < 400 else "http_error", "status_code": status_code, "final_url": final_url, "error": None}
    except urllib.error.HTTPError as exc:
        return {"reachable": 200 <= exc.code < 400, "status": "reachable" if exc.code < 400 else "http_error", "status_code": exc.code, "final_url": url, "error": None}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"reachable": False, "status": "unreachable", "status_code": None, "final_url": None, "error": str(exc.reason if isinstance(exc, urllib.error.URLError) and exc.reason else exc)}
