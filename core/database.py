"""
database.py — SQLite helpers for Rayar RAG.

Stores users, sessions, and runtime settings.
Schema creation is idempotent.
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path("rayar_rag.db")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open a connection with row access by column name."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init(path: Path = DB_PATH) -> None:
    """Create tables if they don't exist. Safe to call repeatedly."""
    with connect(path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            username       TEXT UNIQUE NOT NULL,
            password_hash  TEXT NOT NULL,
            salt           TEXT NOT NULL,
            email          TEXT,
            role           TEXT NOT NULL DEFAULT 'user',
            collections    TEXT NOT NULL DEFAULT '[]',
            can_create_kb  INTEGER NOT NULL DEFAULT 0,
            ai_enabled     INTEGER NOT NULL DEFAULT 1,
            created        REAL NOT NULL,
            last_login     REAL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token    TEXT PRIMARY KEY,
            user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created  REAL NOT NULL,
            expires  REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key      TEXT PRIMARY KEY,
            value    TEXT NOT NULL,
            updated  REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires);
        CREATE INDEX IF NOT EXISTS idx_users_username   ON users(username);
        """)


def get_setting(key: str, default: Any = None, path: Path = DB_PATH) -> Any:
    """Read a JSON-encoded setting."""
    with connect(path) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return row["value"]


def set_setting(key: str, value: Any, path: Path = DB_PATH) -> None:
    """Write a setting as JSON."""
    encoded = json.dumps(value)
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO settings(key, value, updated) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
            (key, encoded, time.time()),
        )


def delete_setting(key: str, path: Path = DB_PATH) -> None:
    with connect(path) as conn:
        conn.execute("DELETE FROM settings WHERE key=?", (key,))


def user_count(path: Path = DB_PATH) -> int:
    """How many users exist. Used to detect first run."""
    with connect(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
