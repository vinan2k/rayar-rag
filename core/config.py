"""
config.py — Configuration loader for Rayar RAG.

Reads config.yaml. Provides typed access with sensible defaults.
Raises clearly if config is missing or malformed.
"""

from pathlib import Path
from typing import Any, Dict
import yaml

CONFIG_PATH = Path("config.yaml")

DEFAULTS: Dict[str, Any] = {
    "app": {
        "name": "Rayar RAG",
        "port": 8501,
        "host": "0.0.0.0",
    },
    "backend": {
        "type": "ollama",              # or "openai-compatible"
        "url": "http://localhost:11434",
        "api_key": "",                 # ignored by Ollama
        "chat_model": "",
        "embed_model": "nomic-embed-text",
        "keep_alive": "5m",            # Ollama only
        "num_ctx": None,               # Ollama only; None leaves the model's own
    },
    "ollama": {
        "url": "http://localhost:11434",
        "default_model": "",
        "embed_model": "nomic-embed-text",
        "keep_alive": "5m",
    },
    "storage": {
        "chroma_dir": "./chroma_db",
        "ingested_files": "./ingested_files",
        "backup_path": "",
    },
    "branding": {
        "primary_color": "#6B1A2A",
        "accent_color": "#B8924D",
        "background_color": "#F7F3EA",
        "text_color": "#1A1A1A",
        "logo": "",
    },
    "features": {
        "imagegen": {"enabled": False, "url": "", "comfyui_dir": ""},
        "whisper": {"enabled": False, "url": ""},
        "filegen": {"enabled": False, "url": ""},
    },
    "auth": {
        "session_days": 30,
        "max_login_attempts": 5,
        "lockout_seconds": 60,
    },
    "watch": {
        "folder": "",                  # scheduled ingest reads from here
        "processed": "",               # blank puts it beside the watched folder
        "failed": "",
        "default_collection": "inbox", # for files not in a subfolder
    },
    "retrieval": {
        "top_k": 15,
        "chunk_size": 800,
        "chunk_overlap": 100,
    },
    "tunnel": {
        "type": "none",
        "dockflare": {"enabled": False, "domain": ""},
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, recursing into nested dicts."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    """Loaded configuration. Access via dot-path: cfg.get('ollama.url')."""

    def __init__(self, data: dict):
        self._data = data

    def get(self, path: str, default: Any = None) -> Any:
        """Get a value by dot-path, e.g. 'ollama.url'."""
        node = self._data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, path: str, value: Any) -> None:
        """Set a value by dot-path. Creates intermediate dicts as needed."""
        parts = path.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    def to_dict(self) -> dict:
        return dict(self._data)

    def save(self, path: Path = CONFIG_PATH) -> None:
        """Write config to disk."""
        with open(path, "w") as f:
            yaml.safe_dump(self._data, f, default_flow_style=False, sort_keys=False)


def exists(path: Path = CONFIG_PATH) -> bool:
    """True if a config file is present."""
    return path.exists()


def load(path: Path = CONFIG_PATH) -> Config:
    """Load config.yaml, merged over defaults. Raises if the file is missing."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run the setup wizard or copy config.yaml.example."
        )
    with open(path) as f:
        user_data = yaml.safe_load(f) or {}
    merged = _deep_merge(DEFAULTS, user_data)
    return Config(merged)


def create_default() -> Config:
    """Return a Config populated with defaults only. Used by the setup wizard."""
    return Config(_deep_merge(DEFAULTS, {}))
