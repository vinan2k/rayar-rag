#!/usr/bin/env python3
"""
watch.py — Index whatever has appeared in a folder.

Run on a schedule. It walks a directory, indexes anything it has not seen
before, and moves each file aside once it is done so the same work is never
repeated.

A subfolder is a collection. Dropping a report into watch/client-reports puts
it in the collection called client-reports, and nothing has to decide anything.
The alternative — asking a model which collection a document belongs in — fails
quietly when it is wrong: a misfiled document is worse than one in a general
collection, because nobody thinks to look for it.

Files are moved rather than tracked in a list. The filesystem is then the
record of what has been done, which survives a lost database, is readable
without tooling, and makes a reprocess as simple as moving a file back.

Uses the same config.yaml as the application, so the backend and the embedding
model are necessarily the same ones. An embedding model that differs between
this and the interface would degrade retrieval without erroring.

    python watch.py                     # folder from config.yaml
    python watch.py --folder ~/inbox    # or given here
    python watch.py --dry-run           # say what would happen, do nothing
"""

import argparse
import logging
import re
import shutil
import sys
import time
from pathlib import Path

from core import config, models
from core.embeddings import VectorStore
from core.ingest import SUPPORTED_EXTENSIONS, chunk_text, extract, missing_reader

log = logging.getLogger("watch")


def slugify(name: str) -> str:
    """
    A folder name as a collection name.

    ChromaDB accepts letters, numbers, dots, underscores and hyphens, must
    start and end with a letter or number, and wants at least three characters.
    Spaces and punctuation are common in folder names, so they are converted
    rather than rejected: a person who made a folder called "Client Reports
    2026" meant that to work.
    """
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip())
    slug = slug.strip("-._")

    # A name with no usable characters at all — one written in a script this
    # cannot transliterate — would otherwise become the same word as every
    # other such name, quietly merging separate folders into one collection.
    # A short digest of the original keeps them distinct and stable.
    if not slug:
        import hashlib
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        return f"collection-{digest}"

    if len(slug) < 3:
        slug = f"col-{slug}"
    return slug[:512]


def find_files(folder: Path, exclude: set[Path]) -> dict[str, list[Path]]:
    """
    Every supported file, grouped by the collection it belongs to.

    Files directly in the watched folder have no subfolder to name them, so
    they are grouped under an empty key and the caller applies a default.
    """
    grouped: dict[str, list[Path]] = {}

    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if any(parent in exclude for parent in path.parents):
            continue

        relative = path.relative_to(folder)
        collection = relative.parts[0] if len(relative.parts) > 1 else ""
        grouped.setdefault(collection, []).append(path)

    return grouped


def ingest_file(path: Path, collection: str, store: VectorStore,
                cfg) -> tuple[bool, str, int]:
    """Index one file. Returns (succeeded, message, passages)."""
    package = missing_reader(path)
    if package:
        return False, f"needs the {package} package", 0

    try:
        text = extract(path)
    except Exception as e:
        return False, f"extraction failed: {e}", 0

    if not text or not text.strip():
        return False, "no text could be read, possibly a scanned document", 0

    chunks = chunk_text(
        text,
        cfg.get("retrieval.chunk_size", 800),
        cfg.get("retrieval.chunk_overlap", 100),
    )
    if not chunks:
        return False, "produced no text worth indexing", 0

    try:
        added = store.add_chunks(collection, chunks, source=path.name)
    except Exception as e:
        return False, f"indexing failed: {e}", 0

    return True, f"{added} passages", added


def move_aside(path: Path, root: Path, destination: Path,
               collection: str) -> Path:
    """
    Move a finished file out of the watched folder.

    A name that already exists is suffixed rather than overwritten. Two
    documents sharing a filename are usually two different documents.
    """
    target_dir = destination / collection if collection else destination
    target_dir.mkdir(parents=True, exist_ok=True)

    target = target_dir / path.name
    if target.exists():
        stem, suffix = path.stem, path.suffix
        target = target_dir / f"{stem}-{int(time.time())}{suffix}"

    shutil.move(str(path), str(target))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Index new documents found in a folder."
    )
    parser.add_argument("--folder", help="Folder to watch. Overrides config.")
    parser.add_argument("--collection",
                        help="Collection for files not in a subfolder.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would happen without doing it.")
    parser.add_argument("--quiet", action="store_true",
                        help="Log warnings and errors only.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not config.exists():
        log.error("No config.yaml. Run the application once to create one.")
        return 1
    cfg = config.load()

    folder_setting = args.folder or cfg.get("watch.folder", "")
    if not folder_setting:
        log.error("No folder to watch. Use --folder, or set watch.folder "
                  "in config.yaml.")
        return 1

    folder = Path(folder_setting).expanduser().resolve()
    if not folder.is_dir():
        log.error("%s is not a directory.", folder)
        return 1

    processed = Path(
        cfg.get("watch.processed") or (folder.parent / f"{folder.name}-processed")
    ).expanduser().resolve()
    failed = Path(
        cfg.get("watch.failed") or (folder.parent / f"{folder.name}-failed")
    ).expanduser().resolve()

    default_collection = (
        args.collection or cfg.get("watch.default_collection") or "inbox"
    )

    grouped = find_files(folder, exclude={processed, failed})
    total = sum(len(v) for v in grouped.values())
    if not total:
        log.info("Nothing new in %s", folder)
        return 0

    log.info("%d file%s in %s", total, "" if total == 1 else "s", folder)

    backend = models.create(cfg)
    if not backend.is_reachable():
        log.error("Cannot reach %s at %s. Nothing indexed.",
                  backend.name, backend.url)
        return 1

    embed_model = cfg.get("backend.embed_model") or cfg.get("ollama.embed_model")
    store = VectorStore(cfg.get("storage.chroma_dir"), backend, embed_model)
    existing = set(store.list_collections())

    indexed = skipped = failures = 0

    for raw_name, paths in sorted(grouped.items()):
        collection = slugify(raw_name) if raw_name else slugify(default_collection)

        if raw_name and collection != raw_name:
            log.info("Folder %r indexes as collection %r", raw_name, collection)
        if collection not in existing:
            log.info("Creating collection %r", collection)
            existing.add(collection)

        # A document already in the collection is left alone. Replacing it
        # would mean deciding that the file on disk is newer, which the
        # filesystem cannot reliably tell us.
        already = set(store.sources_in(collection))

        for path in paths:
            if path.name in already:
                log.info("  %s already in %s, moved aside", path.name, collection)
                if not args.dry_run:
                    move_aside(path, folder, processed, collection)
                skipped += 1
                continue

            if args.dry_run:
                log.info("  would index %s into %s", path.name, collection)
                continue

            ok, message, _ = ingest_file(path, collection, store, cfg)
            if ok:
                log.info("  %s → %s, %s", path.name, collection, message)
                move_aside(path, folder, processed, collection)
                indexed += 1
            else:
                log.warning("  %s failed: %s", path.name, message)
                move_aside(path, folder, failed, collection)
                failures += 1

    if args.dry_run:
        log.info("Dry run. Nothing was indexed or moved.")
        return 0

    log.info("Indexed %d, skipped %d, failed %d", indexed, skipped, failures)
    if failures:
        log.info("Failed files are in %s. A file that yields no text is "
                 "usually scanned, and there is no OCR.", failed)

    return 0


if __name__ == "__main__":
    sys.exit(main())
