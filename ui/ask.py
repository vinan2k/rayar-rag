"""
ask.py — Question and answer against a collection.

The answer and its sources sit side by side. Inline markers in the answer carry
the same numbers as the ledger beside it, so a claim can be checked without
scrolling away from it.

Results are cached against the question that produced them. Streamlit reruns
the whole script on any widget change, so without a cache, opening a source
would re-run the original question.
"""

import html
import re

import streamlit as st

from core import rag
from core.config import Config
from core.embeddings import VectorStore
from core.models import Backend, ContextTooSmall
from ui import sources, tips

CITE_PATTERN = re.compile(r"\[(\d{1,2})\]")
SCOPE = "ask"


def _render_answer(text: str) -> str:
    """Escape the answer, then set [n] markers as references."""
    escaped = html.escape(text)
    marked = CITE_PATTERN.sub(r'<span class="rr-cite-mark">\1</span>', escaped)
    paragraphs = [p.strip() for p in marked.split("\n") if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paragraphs)


def show(
    cfg: Config,
    store: VectorStore,
    backend: Backend,
    collection: str,
    model: str,
    user: dict | None = None,
) -> None:
    """Render the Ask tab."""
    cache_key = f"ask::{collection}"
    left, right = st.columns([2, 1], gap="large")

    with left:
        question = st.text_input(
            "Ask a question",
            key=f"q::{collection}",
            placeholder="What do these documents say about the funding mechanism?",
            label_visibility="collapsed",
        )

    cached = st.session_state.get(cache_key)

    if question and (cached is None or cached["question"] != question):
        with left:
            with st.spinner("Searching the collection…"):
                try:
                    text, results = rag.answer(
                        store, backend, collection, question, model=model,
                        top_k=cfg.get("retrieval.top_k", 15),
                    )
                except ContextTooSmall as e:
                    st.error(str(e))
                    return
        cached = {
            "question": question,
            "answer": text,
            "sources": rag.unique_sources(results),
            "results": results,
        }
        st.session_state[cache_key] = cached
        sources.clear(SCOPE, collection)

    with right:
        st.markdown(
            sources.ledger(
                cached["sources"] if cached else [],
                "Sources",
                "Sources appear here once you ask a question. Every answer is "
                "traceable to the documents it came from.",
            ),
            unsafe_allow_html=True,
        )
        if cached:
            sources.controls(SCOPE, cached["sources"], cfg, store, backend,
                             collection, model)

    with left:
        if not cached:
            return

        if user:
            tips.show("first_answer", user)

        st.markdown('<div class="rr-eyebrow">Answer</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="rr-answer">{_render_answer(cached["answer"])}</div>',
                    unsafe_allow_html=True)

        with st.expander("Retrieved excerpts"):
            docs = cached["results"]["documents"][0]
            metas = cached["results"]["metadatas"][0]
            for i, (doc, meta) in enumerate(zip(docs, metas), 1):
                source = html.escape(meta.get("source", "unknown"))
                st.markdown(f'<div class="rr-eyebrow">{i} &middot; {source}</div>',
                            unsafe_allow_html=True)
                st.text(doc[:700] + ("…" if len(doc) > 700 else ""))

        sources.result(SCOPE, collection)
