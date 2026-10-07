"""Reusable source ledger and source-level drill-down."""

from __future__ import annotations

import html
from collections.abc import Callable

from nicegui import run, ui

from core import doc_links, rag
from core.models import ContextTooSmall


def _excerpt(text: str, limit: int = 700) -> str:
    text = text.strip()
    return text[:limit] + ("…" if len(text) > limit else "")


class SourcePanel:
    def __init__(
        self,
        *,
        cfg,
        store,
        backend,
        get_collection: Callable[[], str | None],
        get_model: Callable[[], str | None],
        result_container=None,
        title: str = "Sources",
        empty_message: str = (
            "Sources appear here once you ask a question. "
            "Every answer is traceable to the documents it came from."
        ),
    ):
        self.cfg = cfg
        self.store = store
        self.backend = backend
        self.get_collection = get_collection
        self.get_model = get_model
        self.title = title
        self.empty_message = empty_message
        self.sources: list[tuple[str, int]] = []
        self.container = ui.element("div").classes("w-full")
        self.result_container = result_container or ui.element("div").classes("w-full")
        self.render()

    def clear_result(self) -> None:
        self.result_container.clear()

    def set_sources(self, sources: list[tuple[str, int]], title: str | None = None) -> None:
        self.sources = list(sources)
        if title:
            self.title = title
        self.clear_result()
        self.render()

    def render(self) -> None:
        self.container.clear()
        with self.container:
            with ui.element("div").classes("rr-ledger"):
                ui.html(f'<div class="rr-ledger-title">{html.escape(self.title)}</div>')
                if not self.sources:
                    ui.html(f'<div class="rr-empty">{html.escape(self.empty_message)}</div>')
                    return

                collection = self.get_collection()
                for i, (name, count) in enumerate(self.sources, 1):
                    unit = "passage" if count == 1 else "passages"
                    path = doc_links.resolve(name, self.cfg, collection)
                    # The row stays plain HTML so the grid in themes.py applies
                    # as written. A NiceGUI container here would insert its own
                    # element between the grid and its columns.
                    ui.html(
                        '<div class="rr-source-row">'
                        f'<span class="rr-source-n">{i}</span><div>'
                        f'<div class="rr-source-name">{html.escape(name)}</div>'
                        f'<div class="rr-source-count">{count} {unit}</div>'
                        '</div></div>'
                    )
                    if path:
                        ui.button(
                            "Download",
                            icon="download",
                            on_click=lambda p=path, n=name: ui.download(p, n),
                        ).props("flat dense size=sm no-caps").classes("rr-dl")

                with ui.element("div").classes("rr-open"):
                    ui.html('<div class="rr-eyebrow">Open one</div>')
                    names = [name for name, _ in self.sources]
                    picker = ui.select(names, value=names[0], label="Document") \
                        .classes("w-full").props("outlined dense")
                    q = ui.input(placeholder="Ask about this document") \
                        .classes("w-full mt-3").props("outlined dense")

                    async def do_summary() -> None:
                        collection, model = self.get_collection(), self.get_model()
                        if not collection or not model or not picker.value:
                            return
                        try:
                            summary = await run.io_bound(
                                rag.summarize, self.store, self.backend,
                                collection, picker.value, model
                            )
                            self._render_summary(picker.value, summary)
                        except ContextTooSmall as exc:
                            ui.notify(str(exc), type="negative", multi_line=True)
                        except Exception as exc:
                            ui.notify(f"Summary failed: {exc}", type="negative", multi_line=True)

                    async def do_ask() -> None:
                        collection, model = self.get_collection(), self.get_model()
                        question = (q.value or "").strip()
                        if not collection or not model or not picker.value or not question:
                            ui.notify("Enter a question about the selected document.")
                            return
                        try:
                            text, results = await run.io_bound(
                                rag.answer, self.store, self.backend,
                                collection, question, model,
                                self.cfg.get("retrieval.top_k", 15), 0.3,
                                {"source": picker.value},
                            )
                            self._render_answer(picker.value, question, text, results)
                        except ContextTooSmall as exc:
                            ui.notify(str(exc), type="negative", multi_line=True)
                        except Exception as exc:
                            ui.notify(f"Source question failed: {exc}", type="negative", multi_line=True)

                    ui.button("Summarise it", icon="summarize", on_click=do_summary) \
                        .classes("w-full mt-2").props("outline color=primary")
                    ui.button("Ask this source", icon="search", on_click=do_ask) \
                        .classes("w-full mt-2").props("unelevated color=primary")
                    q.on("keydown.enter", do_ask)

    def _render_summary(self, source: str, summary: str) -> None:
        self.result_container.clear()
        with self.result_container:
            with ui.element("div").classes("rr-result"):
                ui.html(f'<div class="rr-eyebrow">{html.escape(source)} · summary</div>')
                ui.markdown(summary).classes("w-full")

    def _render_answer(self, source: str, question: str, text: str, results: dict) -> None:
        self.result_container.clear()
        with self.result_container:
            with ui.element("div").classes("rr-result"):
                ui.html(f'<div class="rr-eyebrow">{html.escape(source)} · source question</div>')
                ui.label(question).classes("text-sm opacity-70 mb-3")
                ui.markdown(text).classes("w-full")
                with ui.expansion("Passages from this document", icon="article") \
                        .classes("w-full mt-3").props("dense"):
                    docs = results.get("documents", [[]])[0]
                    metas = results.get("metadatas", [[]])[0]
                    for i, (doc, meta) in enumerate(zip(docs, metas), 1):
                        pos = meta.get("chunk_index", "?")
                        ui.html(f'<div class="rr-eyebrow">{i} · passage {html.escape(str(pos))}</div>')
                        ui.html(f'<div class="rr-excerpt">{html.escape(_excerpt(doc))}</div>')
