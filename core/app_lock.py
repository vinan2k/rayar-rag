"""Single-process guard for Rayar RAG frontends and ingestion jobs."""

from __future__ import annotations

import fcntl
import os
import socket
from pathlib import Path
from typing import IO

_LOCK_HANDLE: IO[str] | None = None


class AlreadyRunning(RuntimeError):
    """Raised when another Rayar process appears to own the data store."""


def port_is_open(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def acquire(
    lock_path: str | Path = ".rayar-rag.lock",
    *,
    refuse_port: int | None = 8501,
) -> None:
    """Hold an exclusive OS lock until this process exits.

    ``refuse_port`` protects against the existing Streamlit app, which predates
    this lock and therefore cannot participate in it yet.
    """
    global _LOCK_HANDLE

    if _LOCK_HANDLE is not None:
        return

    if refuse_port and port_is_open("127.0.0.1", refuse_port):
        raise AlreadyRunning(
            f"Port {refuse_port} is already accepting connections. "
            "The existing Rayar/Streamlit process appears to still be running. "
            "Stop it before starting NiceGUI."
        )

    path = Path(lock_path)
    handle = open(path, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise AlreadyRunning(
            f"Another Rayar process already holds {path}. "
            "Stop that process before starting this one."
        ) from None

    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    _LOCK_HANDLE = handle
