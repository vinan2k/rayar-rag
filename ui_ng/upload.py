"""NiceGUI Upload view using the existing Rayar ingest pipeline."""

from __future__ import annotations

import inspect
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nicegui import events, run, ui

from core.ingest import SUPPORTED_EXTENSIONS, chunk_text, extract, missing_reader
from ui_ng.sources import SourcePanel


@dataclass
class PendingFile:
    name: str
    data: bytes


def _keep_original(temp_path: Path, name: str, cfg) -> list[str]:
    problems = []
    for setting, label in (
        ("storage.ingested_files", "local copy"),
        ("storage.backup_path", "backup"),
    ):
        target = (cfg.get(setting) or "").strip()
        if not target:
            continue
        try:
            directory = Path(target).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(temp_path), str(directory / name))
        except Exception as exc:
            problems.append(f"{label} failed: {exc}")
    return problems


def _ingest_bytes(
    item: PendingFile,
    target: str,
    store,
    cfg,
    replace: bool,
) -> tuple[bool, str, int]:
    """Mirror the current Streamlit _ingest_one, but from uploaded bytes."""
    name = Path(item.name.replace("\\", "/")).name
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return False, f"{suffix} is not a supported format", 0

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        temp.write(item.data)
        temp.close()
        temp_path = Path(temp.name)

        package = missing_reader(temp_path)
        if package:
            return False, f"needs the {package} package installed", 0

        text = extract(temp_path)
        if not text or not text.strip():
            return False, "no text could be read from it", 0

        if replace:
            store.delete_source(target, name)

        chunks = chunk_text(
            text,
            cfg.get("retrieval.chunk_size", 800),
            cfg.get("retrieval.chunk_overlap", 100),
        )
        if not chunks:
            return False, "produced no text worth indexing", 0

        added = store.add_chunks(target, chunks, source=name)
        problems = _keep_original(temp_path, name, cfg)
        message = f"{added} passages"
        if problems:
            message += " — " + "; ".join(problems)
        return True, message, added
    except Exception as exc:
        return False, str(exc), 0
    finally:
        Path(temp.name).unlink(missing_ok=True)


async def _upload_name_and_bytes(e: Any) -> tuple[str, bytes]:
    """Support current NiceGUI uploads plus older event objects gracefully."""
    file_obj = getattr(e, "file", None)
    if file_obj is not None:
        name = Path(str(getattr(file_obj, "name", "upload.bin")).replace("\\", "/")).name
        data = file_obj.read()
        if inspect.isawaitable(data):
            data = await data
        return name, bytes(data)

    # Compatibility with NiceGUI releases where UploadEventArguments exposed
    # e.name / e.content instead of e.file.
    name = Path(str(getattr(e, "name", "upload.bin")).replace("\\", "/")).name
    content = getattr(e, "content", None)
    if content is None:
        raise RuntimeError("NiceGUI upload event did not contain file content.")
    data = content.read()
    if inspect.isawaitable(data):
        data = await data
    return name, bytes(data)


class UploadView:
    def __init__(
        self,
        *,
        cfg,
        store,
        backend,
        get_collection,
        get_model,
        get_user,
        on_collections_changed,
    ):
        self.cfg = cfg
        self.store = store
        self.backend = backend
        self.get_collection = get_collection
        self.get_model = get_model
        self.get_user = get_user
        self.on_collections_changed = on_collections_changed
        self.pending: dict[str, PendingFile] = {}
        self.last_batch: list[tuple[str, int]] = []
        self.batch_collection: str | None = None
        self.pending_label = None
        self.uploader = None

        with ui.element("div").classes("rr-main-grid w-full"):
            with ui.element("main").classes("rr-left"):
                ui.html('<div class="rr-eyebrow">Upload & ingest</div>')
                self.controls = ui.element("div").classes("w-full")
                self.status = ui.element("div").classes("w-full mt-4")
                self.result = ui.element("div").classes("w-full")
            with ui.element("aside").classes("rr-right"):
                self.source_panel = SourcePanel(
                    cfg=cfg,
                    store=store,
                    backend=backend,
                    get_collection=self._result_collection,
                    get_model=get_model,
                    result_container=self.result,
                    title="Added",
                    empty_message=(
                        "Documents appear here once they are indexed. "
                        "Any of them can then be summarised or questioned."
                    ),
                )
        self.render_controls()

    def _result_collection(self) -> str | None:
        return self.batch_collection or self.get_collection()

    def refresh_destination(self) -> None:
        """Update destination controls without discarding the last upload batch."""
        self.render_controls()

    def render_controls(self) -> None:
        self.controls.clear()
        user = self.get_user() or {}
        current = self.get_collection()

        with self.controls:
            with ui.element("div").classes("rr-upload-panel"):
                if current:
                    options = [f"Add to {current}"]
                    if user.get("can_create_kb"):
                        options.append("Start a new collection")
                    destination = ui.radio(options, value=options[0]).props("inline")
                elif user.get("can_create_kb"):
                    destination = ui.radio(
                        ["Start a new collection"], value="Start a new collection"
                    )
                    destination.disable()
                else:
                    ui.html(
                        '<div class="rr-alert">You do not have an accessible collection '
                        'and this account cannot create one.</div>'
                    )
                    return

                new_name = ui.input(
                    "New collection name", placeholder="client-reports"
                ).classes("w-full mt-2").props("outlined dense")
                new_name.set_visibility(not current)

                def destination_changed() -> None:
                    new_name.set_visibility(destination.value == "Start a new collection")

                destination.on_value_change(lambda _: destination_changed())

                ui.label("Select or drop files").classes("text-sm mt-3 mb-1")
                self.uploader = ui.upload(
                    on_upload=self._on_upload,
                    on_rejected=lambda: ui.notify(
                        "One or more files were rejected.", type="negative"
                    ),
                    multiple=True,
                    auto_upload=True,
                ).classes("w-full").props("flat bordered color=primary")

                allowed = ",".join(sorted(SUPPORTED_EXTENSIONS))
                self.uploader.props(f'accept="{allowed}"')

                replace = ui.checkbox(
                    "Replace documents already present", value=False
                ).classes("mt-2")
                self.pending_label = ui.label(
                    f"{len(self.pending)} file(s) ready to ingest."
                    if self.pending else "No files selected."
                ).classes("text-sm opacity-70 mt-2")

                def clear_pending() -> None:
                    self.pending.clear()
                    if self.pending_label:
                        self.pending_label.set_text("No files selected.")
                    if self.uploader:
                        try:
                            self.uploader.reset()
                        except Exception:
                            pass

                with ui.row().classes("items-center gap-2 mt-3"):
                    ingest_button = ui.button(
                        "Ingest selected files", icon="upload"
                    ).props("unelevated color=primary")
                    ui.button("Clear", on_click=clear_pending).props("flat")

                async def ingest_batch() -> None:
                    target = current
                    if destination.value == "Start a new collection":
                        target = (new_name.value or "").strip()
                        valid, why = self.store.validate_name(target)
                        if not valid:
                            ui.notify(why, type="negative")
                            return
                    if not target:
                        ui.notify("Choose or name a destination collection.", type="negative")
                        return
                    if not self.pending:
                        ui.notify("Select at least one file.")
                        return

                    ingest_button.disable()
                    self.status.clear()
                    self.result.clear()
                    ingested: list[tuple[str, int]] = []
                    skipped: list[str] = []
                    failed: list[tuple[str, str]] = []
                    existing = set(self.store.sources_in(target))

                    with self.status:
                        progress = ui.linear_progress(value=0).classes("w-full")
                        message = ui.label("Starting…").classes("text-sm")

                    items = list(self.pending.values())
                    try:
                        for i, item in enumerate(items, 1):
                            safe_name = Path(item.name.replace("\\", "/")).name
                            if safe_name in existing and not replace.value:
                                skipped.append(safe_name)
                                progress.value = i / len(items)
                                progress.update()
                                message.set_text(f"Skipped {safe_name}")
                                continue

                            message.set_text(f"Indexing {safe_name}…")
                            ok, msg, passages = await run.io_bound(
                                _ingest_bytes,
                                item,
                                target,
                                self.store,
                                self.cfg,
                                bool(replace.value),
                            )
                            if ok:
                                ingested.append((safe_name, passages))
                                existing.add(safe_name)
                            else:
                                failed.append((safe_name, msg))
                            progress.value = i / len(items)
                            progress.update()

                        self.batch_collection = target
                        self.last_batch = ingested
                        self.source_panel.set_sources(ingested, title="Added")
                        clear_pending()

                        self.status.clear()
                        with self.status:
                            if ingested:
                                ui.label(
                                    f"{len(ingested)} file(s) added to {target}."
                                ).classes("text-positive")
                            if skipped:
                                ui.label(
                                    f"{len(skipped)} already-present file(s) skipped."
                                ).classes("text-sm opacity-70")
                            for name, msg in failed:
                                ui.label(f"{name}: {msg}").classes("text-sm text-negative")

                        if ingested:
                            self.on_collections_changed(target)
                    finally:
                        ingest_button.enable()

                ingest_button.on_click(ingest_batch)

    async def _on_upload(self, e: events.UploadEventArguments) -> None:
        try:
            safe_name, data = await _upload_name_and_bytes(e)
            self.pending[safe_name] = PendingFile(safe_name, data)
            if self.pending_label:
                self.pending_label.set_text(
                    f"{len(self.pending)} file(s) ready to ingest."
                )
        except Exception as exc:
            ui.notify(f"Could not read upload: {exc}", type="negative", multi_line=True)
