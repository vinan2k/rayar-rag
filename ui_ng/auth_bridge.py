"""Compatibility wrapper around Rayar RAG's existing core.auth module."""

from __future__ import annotations

import json
from typing import Any

from core import auth as core_auth


class AuthAPIError(RuntimeError):
    pass


def _as_dict(value: Any) -> dict | None:
    """Normalize sqlite.Row/dict-like user records."""
    if value is None or value is False:
        return None
    if isinstance(value, dict):
        return dict(value)
    try:
        return dict(value)
    except Exception:
        return None


def _successful_result(username: str, result: Any) -> dict | None:
    """
    Turn the result of core.auth.verify into a user record without changing
    the project's authentication implementation.
    """
    # Some auth APIs return the user record directly.
    user = _as_dict(result)
    if user:
        return user

    # Some return (True, user) or (user, ...).
    if isinstance(result, (tuple, list)):
        for item in result:
            user = _as_dict(item)
            if user:
                return user
        if result and isinstance(result[0], bool) and not result[0]:
            return None

    # Rayar may return only True/False from verify(). On success, retrieve the
    # already-existing user record from the same auth module.
    if result is True or (result and not isinstance(result, (str, bytes))):
        getter = getattr(core_auth, "get_user", None)
        if callable(getter):
            return _as_dict(getter(username))

    return None


def authenticate(username: str, password: str) -> dict | None:
    """
    Authenticate using the project's existing core.auth implementation.

    Current Rayar exposes `verify`; no password hashing is duplicated here.
    """
    verify = getattr(core_auth, "verify", None)
    if callable(verify):
        try:
            result = verify(username, password)
        except TypeError as exc:
            raise AuthAPIError(
                f"core.auth.verify exists but its signature did not accept "
                f"(username, password): {exc}"
            ) from exc

        user = _successful_result(username, result)
        if not user:
            return None

        touch = getattr(core_auth, "touch_login", None)
        if callable(touch):
            try:
                touch(username)
            except Exception:
                # Login timestamp failure must not invalidate a valid password.
                pass
        return user

    # Compatibility fallback for other Rayar releases.
    for name in ("authenticate", "authenticate_user", "verify_user", "login"):
        fn = getattr(core_auth, name, None)
        if not callable(fn):
            continue
        try:
            result = fn(username, password)
        except TypeError:
            continue
        user = _successful_result(username, result)
        if user:
            return user
        return None

    public = sorted(
        n for n, v in vars(core_auth).items()
        if not n.startswith("_") and callable(v)
    )
    raise AuthAPIError(
        "Could not locate an authentication entry point in core.auth. "
        f"Available callables: {', '.join(public) or '(none)'}."
    )


def create_first_user(username: str, password: str) -> dict | None:
    """Delegate first-user creation to core.auth without duplicating its logic."""
    fn = getattr(core_auth, "create_user", None)
    if not callable(fn):
        raise AuthAPIError("core.auth.create_user is not available.")

    attempts = (
        lambda: fn(
            username, password, role="admin",
            collections=["*"], can_create_kb=True
        ),
        lambda: fn(username, password, "admin", ["*"], True),
        lambda: fn(username, password),
    )

    last: Exception | None = None
    for attempt in attempts:
        try:
            result = attempt()
            return _as_dict(result) or _as_dict(
                getattr(core_auth, "get_user")(username)
                if callable(getattr(core_auth, "get_user", None))
                else None
            )
        except TypeError as exc:
            last = exc

    raise AuthAPIError(
        f"core.auth.create_user signature was not recognized: {last}"
    )


def normalize_user(user: dict) -> dict:
    out = dict(user)
    raw = out.get("collections", [])
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            # Preserve legacy "all" convention as full access.
            raw = ["*"] if raw.lower() == "all" else ([raw] if raw else [])

    out["collections"] = list(raw or [])
    out["can_create_kb"] = bool(out.get("can_create_kb", False))
    out["ai_enabled"] = bool(out.get("ai_enabled", True))
    out["role"] = out.get("role") or "user"
    return out


def allowed_collections(user: dict, all_collections: list[str]) -> list[str]:
    user = normalize_user(user)
    allowed = user.get("collections", [])
    if user.get("role") == "admin" or "*" in allowed:
        return list(all_collections)
    permitted = set(allowed)
    return [name for name in all_collections if name in permitted]
