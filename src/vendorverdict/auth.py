from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Mapping

from fastapi import Request, Response

SESSION_COOKIE_NAME = "vendorverdict_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12


@dataclass(frozen=True)
class AuthSettings:
    """Runtime authentication settings for VendorVerdict."""

    enabled: bool
    username: str
    password: str
    secret: str
    secure_cookie: bool
    max_age_seconds: int = SESSION_MAX_AGE_SECONDS


def get_auth_settings(env: Mapping[str, str] | None = None) -> AuthSettings:
    """Read auth settings from environment variables.

    Auth is intentionally disabled unless either VENDORVERDICT_AUTH_ENABLED is
    truthy or a password is configured. This preserves local developer/test
    ergonomics while making production protection a one-env-var change.
    """

    source = env if env is not None else os.environ
    username = source.get("VENDORVERDICT_AUTH_USERNAME", "admin")
    password = source.get("VENDORVERDICT_AUTH_PASSWORD", "")
    enabled_raw = source.get("VENDORVERDICT_AUTH_ENABLED")
    enabled = _env_bool(enabled_raw, default=bool(password))
    secret = source.get("VENDORVERDICT_AUTH_SECRET") or password or "vendorverdict-local-dev-secret"
    secure_cookie = _env_bool(source.get("VENDORVERDICT_AUTH_SECURE_COOKIE"), default=False)
    max_age = _env_int(source.get("VENDORVERDICT_AUTH_SESSION_SECONDS"), default=SESSION_MAX_AGE_SECONDS)
    return AuthSettings(
        enabled=enabled,
        username=username,
        password=password,
        secret=secret,
        secure_cookie=secure_cookie,
        max_age_seconds=max_age,
    )


def auth_is_configured(settings: AuthSettings | None = None) -> bool:
    settings = settings or get_auth_settings()
    return bool(settings.username and settings.password and settings.secret)


def credentials_are_valid(username: str, password: str, settings: AuthSettings | None = None) -> bool:
    settings = settings or get_auth_settings()
    if not settings.enabled or not auth_is_configured(settings):
        return False
    return hmac.compare_digest(username, settings.username) and hmac.compare_digest(password, settings.password)


def create_session_token(username: str, settings: AuthSettings | None = None, *, now: int | None = None) -> str:
    settings = settings or get_auth_settings()
    issued_at = int(now if now is not None else time.time())
    payload = f"{username}:{issued_at}"
    signature = _sign(payload, settings.secret)
    raw = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def verify_session_token(token: str, settings: AuthSettings | None = None, *, now: int | None = None) -> str | None:
    settings = settings or get_auth_settings()
    if not token or not settings.enabled or not auth_is_configured(settings):
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, issued_at_text, signature = raw.rsplit(":", 2)
        issued_at = int(issued_at_text)
    except Exception:
        return None

    payload = f"{username}:{issued_at}"
    expected = _sign(payload, settings.secret)
    if not hmac.compare_digest(signature, expected):
        return None
    if username != settings.username:
        return None
    current = int(now if now is not None else time.time())
    if current - issued_at > settings.max_age_seconds:
        return None
    return username


def authenticate_basic_header(header_value: str | None, settings: AuthSettings | None = None) -> str | None:
    settings = settings or get_auth_settings()
    if not header_value or not header_value.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(header_value.split(" ", 1)[1]).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return None
    if credentials_are_valid(username, password, settings):
        return username
    return None


def authenticated_username(request: Request, settings: AuthSettings | None = None) -> str | None:
    settings = settings or get_auth_settings()
    if not settings.enabled:
        return None
    basic_user = authenticate_basic_header(request.headers.get("authorization"), settings)
    if basic_user:
        return basic_user
    return verify_session_token(request.cookies.get(SESSION_COOKIE_NAME, ""), settings)


def set_session_cookie(response: Response, username: str, settings: AuthSettings | None = None) -> None:
    settings = settings or get_auth_settings()
    token = create_session_token(username, settings)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=settings.max_age_seconds,
        httponly=True,
        secure=settings.secure_cookie,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _env_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(value: str | None, *, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
