"""NiceGUI Ask view."""

from __future__ import annotations

import html
import re

from nicegui import run, ui

from core import rag
from core.models import ContextTooSmall
from ui_ng.sources import SourcePanel

CITE_PATTERN = re.compile(r"\[(\d{1,2})\]")


def _answer_html(text: str) -> str:
    escaped = html.escape(text)
    marked = CITE_PATTERN.sub(r'<span class="rr-cite-mark">\1</span>', escaped)
    paragraphs = [p.strip() for p in marked.split("\n") if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paragraphs)


def _excerpt(text: str, limit: int = 700) -> str:
    text = text.strip()
    return text[:limit] + ("…" if len(text) > limit else "")


class AskView:
    def __init__(self, *, cfg, store, backend, get_collection, get_model):
        self.cfg = cfg
        self.store = store
        self.backend = backend
        self.get_collection = get_collection
        self.get_model = get_model

        with ui.element("div").classes("rr-main-grid w-full"):
            with ui.element("main").classes("rr-left"):
                ui.html('<div class="rr-eyebrow">Ask</div>')
                with ui.row().classes("w-full items-start gap-3 no-wrap"):
                    self.question = ui.input(
                        placeholder="What do these documents say about the funding mechanism?"
                    ).classes("grow").props("outlined")
                    self.button = ui.button("Ask", icon="arrow_forward") \
                        .props("unelevated color=primary").classes("mt-1")

                self.status_row = ui.row().classes("rr-status items-center gap-2 mt-2")
                with self.status_row:
                    ui.spinner(size="sm")
                    self.status = ui.label("")
                self.status_row.set_visibility(False)

                self.answer = ui.element("div").classes("w-full mt-5")
                self.drill_result = ui.element("div").classes("w-full")

            with ui.element("aside").classes("rr-right"):
                self.sources = SourcePanel(
                    cfg=cfg, store=store, backend=backend,
                    get_collection=get_collection, get_model=get_model,
                    result_container=self.drill_result,
                )

        self.button.on_click(self.ask)
        self.question.on("keydown.enter", self.ask)

    def reset(self) -> None:
        self.answer.clear()
        self.drill_result.clear()
        self.sources.set_sources([])

    def _busy(self, message: str | None) -> None:
        self.status.set_text(message or "")
        self.status_row.set_visibility(bool(message))
        if message:
            self.button.disable()
            self.question.disable()
        else:
            self.button.enable()
            self.question.enable()

    async def ask(self) -> None:
        question = (self.question.value or "").strip()
        collection, model = self.get_collection(), self.get_model()
        if not question:
            ui.notify("Enter a question first.")
            return
        if not collection or not model:
            ui.notify("Select a collection and model.", type="negative")
            return

        self._busy("Searching the collection…")
        self.answer.clear()
        self.drill_result.clear()
        try:
            text, results = await run.io_bound(
                rag.answer, self.store, self.backend,
                collection, question, model,
                self.cfg.get("retrieval.top_k", 15),
            )
            self._render(text, results)
            self.sources.set_sources(rag.unique_sources(results))
        except ContextTooSmall as exc:
            ui.notify(str(exc), type="negative", multi_line=True)
        except Exception as exc:
            ui.notify(f"Ask failed: {exc}", type="negative", multi_line=True)
        finally:
            self._busy(None)

    def _render(self, text: str, results: dict) -> None:
        self.answer.clear()
        with self.answer:
            ui.html('<div class="rr-eyebrow">Answer</div>')
            ui.html(f'<div class="rr-answer">{_answer_html(text)}</div>')
            with ui.expansion("Retrieved excerpts", icon="article") \
                    .classes("w-full mt-4").props("dense"):
                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                for i, (doc, meta) in enumerate(zip(docs, metas), 1):
                    source = meta.get("source", "unknown")
                    pos = meta.get("chunk_index", "?")
                    ui.html(
                        f'<div class="rr-eyebrow">{i} · '
                        f'{html.escape(str(source))} · passage {html.escape(str(pos))}</div>'
                    )
                    ui.html(f'<div class="rr-excerpt">{html.escape(_excerpt(doc))}</div>')
