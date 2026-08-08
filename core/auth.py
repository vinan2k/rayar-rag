"""
auth.py — User management and session handling.

Passwords: PBKDF2-HMAC-SHA256, 200k iterations, per-user salt.
Sessions: opaque tokens with expiry, stored in SQLite.
"""

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from typing import List, Optional

from core.database import connect, DB_PATH

PBKDF_ITERS = 200_000


def _hash_password(password: str, salt: bytes) -> str:
    """Derive a password hash. Returns hex string."""
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF_ITERS
    ).hex()


def create_user(
    username: str,
    password: str,
    role: str = "user",
    email: str = "",
    collections: Optional[List[str]] = None,
    can_create_kb: bool = False,
    path: Path = DB_PATH,
) -> int:
    """Create a user. Returns the new user id. Raises on duplicate username."""
    if collections is None:
        collections = ["all"] if role == "admin" else []
    salt = secrets.token_bytes(16)
    pw_hash = _hash_password(password, salt)
    with connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, salt, email, role, "
            "collections, can_create_kb, ai_enabled, created) "
            "VALUES(?,?,?,?,?,?,?,1,?)",
            (
                username,
                pw_hash,
                salt.hex(),
                email,
                role,
                json.dumps(collections),
                1 if can_create_kb else 0,
                time.time(),
            ),
        )
        return cur.lastrowid


def verify(username: str, password: str, path: Path = DB_PATH) -> Optional[dict]:
    """Check credentials. Returns the user dict on success, None on failure."""
    with connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
    if row is None:
        return None
    salt = bytes.fromhex(row["salt"])
    candidate = _hash_password(password, salt)
    if not hmac.compare_digest(candidate, row["password_hash"]):
        return None
    return _row_to_user(row)


def _row_to_user(row) -> dict:
    """Convert a sqlite3.Row to a plain user dict with parsed collections."""
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"] or "",
        "role": row["role"],
        "collections": json.loads(row["collections"]),
        "can_create_kb": bool(row["can_create_kb"]),
        "ai_enabled": bool(row["ai_enabled"]),
        "created": row["created"],
        "last_login": row["last_login"],
    }


def get_user(username: str, path: Path = DB_PATH) -> Optional[dict]:
    with connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
    return _row_to_user(row) if row else None


def list_users(path: Path = DB_PATH) -> List[dict]:
    with connect(path) as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY username").fetchall()
    return [_row_to_user(r) for r in rows]


def set_password(username: str, password: str, path: Path = DB_PATH) -> bool:
    """Change a password. Returns True if the user existed."""
    salt = secrets.token_bytes(16)
    pw_hash = _hash_password(password, salt)
    with connect(path) as conn:
        cur = conn.execute(
            "UPDATE users SET password_hash=?, salt=? WHERE username=?",
            (pw_hash, salt.hex(), username),
        )
        return cur.rowcount > 0


def update_user(
    username: str,
    role: Optional[str] = None,
    collections: Optional[List[str]] = None,
    can_create_kb: Optional[bool] = None,
    ai_enabled: Optional[bool] = None,
    email: Optional[str] = None,
    path: Path = DB_PATH,
) -> bool:
    """Update user fields. Only non-None arguments are applied."""
    fields, values = [], []
    if role is not None:
        fields.append("role=?")
        values.append(role)
    if collections is not None:
        fields.append("collections=?")
        values.append(json.dumps(collections))
    if can_create_kb is not None:
        fields.append("can_create_kb=?")
        values.append(1 if can_create_kb else 0)
    if ai_enabled is not None:
        fields.append("ai_enabled=?")
        values.append(1 if ai_enabled else 0)
    if email is not None:
        fields.append("email=?")
        values.append(email)
    if not fields:
        return False
    values.append(username)
    with connect(path) as conn:
        cur = conn.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE username=?", values
        )
        return cur.rowcount > 0


def delete_user(username: str, path: Path = DB_PATH) -> bool:
    with connect(path) as conn:
        cur = conn.execute("DELETE FROM users WHERE username=?", (username,))
        return cur.rowcount > 0


def can_access(user: dict, collection: str) -> bool:
    """True if the user may access this collection."""
    allowed = user.get("collections", [])
    return "all" in allowed or collection in allowed


def touch_login(username: str, path: Path = DB_PATH) -> None:
    with connect(path) as conn:
        conn.execute(
            "UPDATE users SET last_login=? WHERE username=?", (time.time(), username)
        )
