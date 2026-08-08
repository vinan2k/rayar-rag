"""
upload.py — Adding documents, then reading what was added.

Laid out like Ask, because the second half of the task is the same task. On the
left, where to put the documents and which ones; on the right, what went in.
Pick one from that list and it can be summarised or questioned, exactly as a
source retrieved by a question can be.

That is the whole reason there is no Summarize tab. Nobody sets out to
summarise in the abstract. They summarise something they just added, or
something an answer surfaced. Both are covered here and in Ask.

Ingesting into a new collection does not switch the collection selector at the
top of the page. Doing so would send the next question somewhere the person did
not choose, with only the corpus strip to tell them.
"""

import shutil
import tempfile
from pathlib import Path

import streamlit as st

from core.config import Config
from core.embeddings import VectorStore
from core.ingest import (SUPPORTED_EXTENSIONS, chunk_text, extract,
                         missing_reader)
from core.models import Backend
from ui import sources, tips

SCOPE = "upload"


def _keep_original(temp_path: Path, name: str, cfg: Config) -> list[str]:
    """
    Copy the file to its keeping places. Returns any failures.

    A backup that cannot be written is worth reporting but not worth failing
    the ingest over: the document is indexed either way.
    """
    problems = []
    for setting, label in (("storage.ingested_files", "local copy"),
                           ("storage.backup_path", "backup")):
        target = (cfg.get(setting) or "").strip()
        if not target:
            continue
        try:
            directory = Path(target).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(temp_path), str(directory / name))
        except Exception as e:
            problems.append(f"{label} failed: {e}")
    return problems


def _ingest_one(uploaded, collection: str, store: VectorStore, cfg: Config,
                replace: bool, on_progress=None) -> tuple[bool, str, int]:
    """
    Index one file. Returns (succeeded, message, passages).

    Written to a temporary path first because every extractor reads from disk,
    and removed afterwards whatever happens.
    """
    name = uploaded.name
    suffix = Path(name).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        return False, f"{suffix} is not a supported format", 0

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        temp.write(uploaded.read())
        temp.close()
        temp_path = Path(temp.name)

        package = missing_reader(temp_path)
        if package:
            return False, f"needs the {package} package installed", 0

        text = extract(temp_path)
        if not text or not text.strip():
            return False, "no text could be read from it", 0

        if replace:
            store.delete_source(collection, name)

        chunks = chunk_text(text, cfg.get("retrieval.chunk_size", 800),
                            cfg.get("retrieval.chunk_overlap", 100))
        if not chunks:
            return False, "produced no text worth indexing", 0

        added = store.add_chunks(collection, chunks, source=name,on_progress=on_progress)
        problems = _keep_original(temp_path, name, cfg)

        message = f"{added} passages"
        if problems:
            message += " — " + "; ".join(problems)
        return True, message, added

    except Exception as e:
        return False, str(e), 0
    finally:
        Path(temp.name).unlink(missing_ok=True)


def show(
    cfg: Config,
    store: VectorStore,
    backend: Backend,
    collection: str,
    user: dict,
    model: str,
) -> None:
    """Render the Upload tab."""
    left, right = st.columns([2, 1], gap="large")

    # One key, not one per collection. On a first run this tab is reached with
    # no collection at all, and the moment documents are indexed the page
    # changes shape: the collection selector appears, the empty state is gone,
    # and a key derived from the collection would no longer match the one the
    # batch was stored under. The batch records which collection it went into,
    # so scoping the key adds nothing and loses everything.
    batch_key = "upload_batch"

    # ---- left: where, what, and the result of opening one -----------------
    with left:
        target = collection
        existing = set(store.sources_in(collection)) if collection else set()

        # On a first run there is nothing to add to, so the only question is
        # what to call the first collection. Offering "add to" against a
        # collection that does not exist would be asking about a choice the
        # person does not have.
        # Held for the session once true. Recomputing it would flip the moment
        # the first collection exists, replacing the name field with a
        # destination radio while the person is still reading the result of
        # what they just did.
        if "upload_first_run" not in st.session_state:
            st.session_state["upload_first_run"] = not store.list_collections()
        first_run = st.session_state["upload_first_run"] and not collection

        if first_run:
            tips.show("first_collection", user)
            target = st.text_input(
                "Name your first collection",
                value="documents",
                help="A set of documents searched together. Letters, numbers, "
                     "dots, underscores and hyphens.",
            )
            if not target:
                st.caption("Give it a name to continue.")
                return
            valid, why = store.validate_name(target)
            if not valid:
                st.error(why)
                return
            existing = set()

        elif user.get("can_create_kb"):
            choice = st.radio(
                "Destination",
                [f"Add to {collection}", "Start a new collection"],
                horizontal=True,
                label_visibility="collapsed",
            )
            if choice == "Start a new collection":
                proposed = st.text_input("Name for the new collection",
                                         placeholder="client-reports")
                if not proposed:
                    st.caption("Enter a name to continue.")
                    return
                valid, why = store.validate_name(proposed)
                if not valid:
                    st.error(why)
                    return
                if proposed in store.list_collections():
                    st.warning(f"{proposed} already exists. Documents will be "
                               "added to it.")
                target = proposed
                existing = set(store.sources_in(proposed))
        else:
            st.caption(f"Adding to {collection}.")

        uploaded = st.file_uploader(
            "Files",
            type=[e.lstrip(".") for e in sorted(SUPPORTED_EXTENSIONS)],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

        # Files already ingested in this session are excluded. The uploader
        # keeps its selection after a batch runs, so without this the clash
        # warning reappears on every rerun, naming documents the person has
        # only just added themselves.
        batch_so_far = st.session_state.get("upload_batch") or {}
        already_done = {n for n, _ in batch_so_far.get("ingested", [])}
        clashes = ([f.name for f in uploaded
                    if f.name in existing and f.name not in already_done]
                   if uploaded else [])
        replace = False
        if clashes:
            st.warning(
                f"{len(clashes)} of these are already in {target}: "
                + ", ".join(clashes[:3]) + ("…" if len(clashes) > 3 else "")
            )
            replace = st.radio(
                "For those already present",
                ["Skip them", "Replace what is there"],
                horizontal=True,
            ).startswith("Replace")

        if uploaded and st.button(f"Add {len(uploaded)} to {target}",
                                  type="primary"):
            progress = st.progress(0.0, text="Starting…")
            ingested, failed, skipped = [], [], []

            for index, item in enumerate(uploaded, 1):
                progress.progress((index - 1) / len(uploaded), text=item.name)
                if item.name in clashes and not replace:
                    skipped.append(item.name)
                    continue

                # Embedding runs one call per passage, so a large document
                # takes minutes. Without this the bar advances only between
                # files, and a single large upload sits at zero throughout.
                def report(done, total, _i=index, _n=item.name):
                    share = (_i - 1 + done / max(total, 1)) / len(uploaded)
                    progress.progress(
                        min(share, 1.0),
                        text=f"{_n} — passage {done} of {total}",
                    )

                ok, message, passages = _ingest_one(item, target, store, cfg,
                                                    replace, on_progress=report)
                if ok:
                    ingested.append((item.name, passages))
                else:
                    failed.append((item.name, message))

            progress.empty()

            st.session_state[batch_key] = {
                "collection": target,
                "ingested": ingested,
                "failed": failed,
                "skipped": skipped,
            }
            sources.clear(SCOPE, target)
            if ingested:
                tips.show("first_upload", user)

        batch = st.session_state.get(batch_key)
        if batch:
            if batch["ingested"]:
                st.success(f"{len(batch['ingested'])} added to "
                           f"{batch['collection']}.")
            if batch["skipped"]:
                st.info(f"{len(batch['skipped'])} skipped as already present.")
            if batch["failed"]:
                st.error(f"{len(batch['failed'])} could not be read.")
                for name, message in batch["failed"]:
                    st.write(f"· **{name}** — {message}")


    # ---- right: what went in, and the way into one ------------------------
    with right:
        batch = st.session_state.get(batch_key)
        listed = batch["ingested"] if batch else []
        st.markdown(
            sources.ledger(
                listed,
                "Added",
                "Documents appear here once they are indexed. Any of them can "
                "then be summarised or questioned.",
            ),
            unsafe_allow_html=True,
        )
        if listed:
            sources.controls(SCOPE, listed, cfg, store, backend,
                             batch["collection"], model)

    # Rendered last, after the controls above have had their chance to write
    # state. Streamlit runs top to bottom, so a result placed in the left
    # column earlier would be drawn before the button that produces it.
    with left:
        if batch:
            sources.result(SCOPE, batch["collection"])
