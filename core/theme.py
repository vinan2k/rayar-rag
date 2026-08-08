"""
theme.py — Reading and switching theme presets.

A theme is a TOML file in themes/. Applying one copies its values into
.streamlit/config.toml rather than pointing at it with `base`.

The pointer form reads better, and Streamlit does support it, but a change to
the referenced file does not take effect until the server restarts: Streamlit
re-reads config.toml on a rerun without re-resolving an external reference.
Written in full, a theme change appears on the next rerun. Verified by
inlining a preset by hand and observing the whole interface change without a
restart.
"""

import re
import tomllib
from pathlib import Path

THEMES_DIR = Path("themes")
CONFIG_PATH = Path(".streamlit/config.toml")

ACTIVE_MARKER = "# rayar-theme:"


def available() -> list[str]:
    """Preset names, without the .toml extension."""
    if not THEMES_DIR.exists():
        return []
    return sorted(p.stem for p in THEMES_DIR.glob("*.toml"))


def _first_comment(path: Path) -> str:
    """The first comment line of a theme file, used as its description."""
    try:
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                text = stripped.lstrip("# ").strip()
                if text:
                    return text
            elif stripped:
                break
    except Exception:
        pass
    return ""


def descriptions() -> dict[str, str]:
    """Map of preset name to its one-line description."""
    return {name: _first_comment(THEMES_DIR / f"{name}.toml") for name in available()}


def active() -> str | None:
    """
    Which preset is currently applied.

    Recorded as a comment when the theme is written, since the values
    themselves carry no name once inlined.
    """
    if not CONFIG_PATH.exists():
        return None
    for line in CONFIG_PATH.read_text().splitlines():
        if line.startswith(ACTIVE_MARKER):
            name = line[len(ACTIVE_MARKER):].strip()
            return name if name in available() else None
    return None


def _format(value) -> str:
    """A Python value as TOML."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format(v) for v in value) + "]"
    return f'"{value}"'


def _preserved_sections(text: str) -> str:
    """
    Everything in the current config that is not the theme.

    Server settings and anything else a person has added survive a theme
    change; only the theme table is replaced.
    """
    lines = text.splitlines()
    kept, in_theme = [], False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            in_theme = stripped.startswith("[theme")
        if not in_theme:
            kept.append(line)
    return "\n".join(kept).strip()


def apply(name: str) -> bool:
    """
    Write a preset's values into config.toml. Returns False if it is missing.

    The values are copied rather than referenced so the change takes effect on
    the next rerun rather than the next restart.
    """
    source = THEMES_DIR / f"{name}.toml"
    if not source.exists():
        return False

    try:
        data = tomllib.loads(source.read_text()).get("theme", {})
    except Exception:
        return False
    if not data:
        return False

    existing = CONFIG_PATH.read_text() if CONFIG_PATH.exists() else ""
    rest = _preserved_sections(existing)

    lines = [
        "# Rayar RAG — active theme.",
        "#",
        "# Written by the appearance picker. Edit freely; the picker only",
        "# rewrites this file when Apply is pressed.",
        f"{ACTIVE_MARKER} {name}",
        "",
        "[theme]",
    ]
    for key, value in data.items():
        lines.append(f"{key} = {_format(value)}")

    output = "\n".join(lines)
    if rest:
        output += "\n\n" + rest
    output += "\n"

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(output)
    return True
