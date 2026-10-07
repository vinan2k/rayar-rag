"""
doc_links.py — Finding the original file behind an indexed document.

ChromaDB stores a document's filename as metadata but not its path, so the
original has to be located on disk by name. That lets an answer offer the
document it came from rather than only naming it.

The index is cached to disk. Walking a large network share takes minutes, and
doing it inside a request blocks the event loop long enough for the browser to
give up on the connection. So the walk happens once, the result is written to
JSON, and startup reads that file instead. Rebuilding is a scheduled job, which
suits a corpus that changes when documents are ingested rather than constantly.

A lookup that misses does not trigger a rebuild. A missing file means no
download control on that row, which is a far smaller cost than a request that
hangs for minutes.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

CACHE_PATH = Path("doc_index.json")

_index: dict[str, list[str]] | None = None


def roots(cfg) -> list[Path]:
    """
    Folders to search, from config.

    storage.ingested_files is always included: documents added through the
    browser are copied there, so it is the one location guaranteed to hold
    originals regardless of how the rest is configured.
    """
    found = []
    for setting in ("storage.ingested_files", "storage.backup_path"):
        value = (cfg.get(setting) or "").strip()
        if value:
            found.append(Path(value).expanduser())

    for entry in cfg.get("storage.source_roots") or []:
        if str(entry).strip():
            found.append(Path(str(entry)).expanduser())

    seen, unique = set(), []
    for path in found:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def build_index(cfg, verbose: bool = False) -> dict[str, list[str]]:
    """
    Walk every root and write the filename-to-paths map to disk.

    Slow by nature on a network share, so this belongs in a scheduled job
    rather than anywhere a person is waiting.
    """
    global _index
    index: dict[str, list[str]] = {}

    for root in roots(cfg):
        if not root.is_dir():
            if verbose:
                print(f"  not reachable: {root}")
            continue
        count = 0
        for dirpath, _, files in os.walk(root):
            for name in files:
                index.setdefault(name, []).append(str(Path(dirpath) / name))
                count += 1
        if verbose:
            print(f"  {count:>8,}  {root}")

    tmp = CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index))
    tmp.replace(CACHE_PATH)   # atomic, so a reader never sees a partial file

    _index = index
    return index


def load_index() -> dict[str, list[str]]:
    """Read the cached index. Empty if it has never been built."""
    global _index
    if _index is not None:
        return _index
    try:
        _index = json.loads(CACHE_PATH.read_text())
    except Exception:
        _index = {}
    return _index


def resolve(source: str, cfg=None, collection: str | None = None) -> Path | None:
    """
    The file behind a source name, or None.

    Where several files share a name, a path containing the collection name is
    preferred: collections are usually ingested from a folder of that name, so
    it is the better guess.
    """
    index = load_index()
    hits = index.get(Path(source).name)
    if not hits:
        return None

    if collection and len(hits) > 1:
        for hit in hits:
            if collection.lower() in hit.lower():
                return Path(hit)
    return Path(hits[0])


def age_days() -> float | None:
    """How old the cache is, or None if there isn't one."""
    try:
        return (time.time() - CACHE_PATH.stat().st_mtime) / 86400
    except OSError:
        return None


def main() -> int:
    """Rebuild the cache. Run from a scheduled job or by hand."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core import config

    started = time.time()
    cfg = config.load()
    print("Indexing source folders:")
    index = build_index(cfg, verbose=True)
    paths = sum(len(v) for v in index.values())
    print(f"\n{len(index):,} filenames, {paths:,} paths, "
          f"{time.time() - started:.0f}s -> {CACHE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
