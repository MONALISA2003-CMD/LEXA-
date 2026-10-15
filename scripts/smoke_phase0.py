#!/usr/bin/env python3
"""Run safe LEXA Phase 0 HTTP acceptance probes.

Anonymous probes are read-only/idempotent. Credentialed E2E creates a session
for an explicitly provided test account, rotates the cookie, verifies identity
and a protected catalog read, then logs out and verifies revocation. Never put
credentials in source control or command-line arguments; use environment vars.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = os.getenv("LEXA_SMOKE_API_URL", "https://lexa-n10e.onrender.com").rstrip("/")
EMAIL = os.getenv("LEXA_SMOKE_EMAIL", "").strip()
PASSWORD = os.getenv("LEXA_SMOKE_PASSWORD", "")
TENANT_ID = os.getenv("LEXA_SMOKE_TENANT_ID", "").strip()
TIMEOUT = float(os.getenv("LEXA_SMOKE_TIMEOUT", "20"))
failures: list[str] = []


def request(opener: urllib.request.OpenerDirector, method: str, path: str,
            body: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None) -> tuple[int, Any, bytes]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Accept": "application/json", **({"Content-Type": "application/json"} if body is not None else {}), **(headers or {})},
        method=method,
    )
    try:
        with opener.open(req, timeout=TIMEOUT) as response:
            raw = response.read()
            status, response_headers = response.status, response.headers
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status, response_headers = exc.code, exc.headers
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    return status, {"headers": response_headers, "payload": payload}, raw


def check(name: str, ok: bool, detail: str) -> None:
    print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    if not ok:
        failures.append(name)


def cookie_value(jar: http.cookiejar.CookieJar) -> str | None:
    return next((c.value for c in jar if c.name == "lexa_refresh_token"), None)


def main() -> int:
    plain = urllib.request.build_opener()
    status, meta, _ = request(plain, "GET", "/health")
    health = meta["payload"] if isinstance(meta, dict) else None
    check("health_liveness", status == 200 and isinstance(health, dict) and health.get("status") == "ok",
          f"HTTP {status}; process liveness only")

    status, meta, _ = request(plain, "GET", "/ready")
    ready = meta["payload"] if isinstance(meta, dict) else None
    deps = ready.get("dependencies", {}) if isinstance(ready, dict) else {}
    cache_present = isinstance(deps, dict) and "cache" in deps
    deps_ok = isinstance(deps, dict) and deps.get("database") == "ok" and deps.get("cache") == "ok"
    check("dependency_readiness", status == 200 and isinstance(ready, dict) and ready.get("status") == "ready" and deps_ok,
          f"HTTP {status}; database={deps.get('database', 'missing')} cache={deps.get('cache', 'missing')} (cache field present={cache_present})")

    status, meta, _ = request(plain, "POST", "/api/v1/auth/refresh")
    payload = meta["payload"]
    detail = payload.get("detail") if isinstance(payload, dict) else None
    check("refresh_without_cookie", status == 401 and status != 422,
          f"HTTP {status}; request body omission must not produce validation 422")

    status, meta, _ = request(plain, "POST", "/api/v1/auth/logout")
    check("logout_without_cookie", status == 200 and isinstance(meta["payload"], dict) and meta["payload"].get("status") == "logged_out",
          f"HTTP {status}; anonymous logout is idempotent")

    if not EMAIL and not PASSWORD:
        print("SKIP credentialed_session_journey: set LEXA_SMOKE_EMAIL and LEXA_SMOKE_PASSWORD for a dedicated test account")
    elif not EMAIL or not PASSWORD:
        check("credential_environment", False, "both LEXA_SMOKE_EMAIL and LEXA_SMOKE_PASSWORD are required")
    else:
        jar = http.cookiejar.CookieJar()
        session_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        login_body: dict[str, Any] = {"email": EMAIL, "password": PASSWORD}
        if TENANT_ID:
            login_body["tenant_id"] = TENANT_ID
        status, meta, _ = request(session_opener, "POST", "/api/v1/auth/login", login_body)
        login_payload = meta["payload"]
        if status == 409 and isinstance(login_payload, dict) and TENANT_ID == "":
            check("credentialed_login", False, "account has multiple workspaces; set LEXA_SMOKE_TENANT_ID to a workspace the test account may access")
        elif status != 200 or not isinstance(login_payload, dict) or not login_payload.get("access_token"):
            detail_code = "unknown"
            if isinstance(login_payload, dict):
                detail = login_payload.get("detail")
                if isinstance(detail, dict):
                    detail_code = str(detail.get("code", "unknown"))
                elif isinstance(detail, str):
                    detail_code = detail
            check("credentialed_login", False, f"HTTP {status}; error code/detail={detail_code}")
        else:
            login_has_cookie = cookie_value(jar) is not None
            check("credentialed_login", login_has_cookie, f"HTTP {status}; refresh cookie present={login_has_cookie}")
            token = str(login_payload["access_token"])
            before_refresh_cookie = cookie_value(jar)
            status, meta, _ = request(session_opener, "POST", "/api/v1/auth/refresh")
            refreshed = meta["payload"]
            after_refresh_cookie = cookie_value(jar)
            refresh_ok = status == 200 and isinstance(refreshed, dict) and bool(refreshed.get("access_token"))
            check("cookie_refresh_rotation", refresh_ok and before_refresh_cookie is not None and after_refresh_cookie is not None and before_refresh_cookie != after_refresh_cookie,
                  f"HTTP {status}; cookie rotated={before_refresh_cookie is not None and after_refresh_cookie is not None and before_refresh_cookie != after_refresh_cookie}")
            if refresh_ok:
                token = str(refreshed["access_token"])
            auth_headers = {"Authorization": f"Bearer {token}"}
            status, meta, _ = request(session_opener, "GET", "/api/v1/auth/me", headers=auth_headers)
            identity = meta["payload"]
            check("authoritative_identity", status == 200 and isinstance(identity, dict) and isinstance(identity.get("workspace"), dict),
                  f"HTTP {status}; /auth/me returns user/workspace context")
            status, _, _ = request(session_opener, "GET", "/api/v1/catalog/products?limit=1", headers=auth_headers)
            check("protected_catalog_read", status == 200, f"HTTP {status}; tenant-scoped product listing is readable")

            old_cookie = cookie_value(jar)
            status, meta, _ = request(session_opener, "POST", "/api/v1/auth/logout")
            check("credentialed_logout", status == 200, f"HTTP {status}")
            # Send the final rotated refresh token explicitly to ensure the server revokes it,
            # even if the cookie jar correctly removed the expired cookie.
            if old_cookie:
                status, _, _ = request(plain, "POST", "/api/v1/auth/refresh", headers={"Cookie": f"lexa_refresh_token={old_cookie}"})
                check("refresh_rejected_after_logout", status == 401, f"HTTP {status}; rotated refresh token cannot be reused")
            status, _, _ = request(plain, "GET", "/api/v1/auth/me", headers=auth_headers)
            check("identity_rejected_after_logout", status == 401, f"HTTP {status}; revoked session no longer authenticates")

    if failures:
        print(f"Phase 0 smoke result: FAIL ({len(failures)} failed checks)")
        return 1
    print("Phase 0 smoke result: PASS for all executed checks; credentialed journey is only covered when dedicated test credentials are supplied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
