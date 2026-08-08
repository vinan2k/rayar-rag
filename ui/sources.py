"""
sources.py — The ledger, and the way into one of its documents.

Two tabs end with a person looking at a short list of documents and wanting to
open one. In Ask the list is what a question retrieved; in Upload it is what
was just ingested. The list arrives differently and everything after it is the
same, so it lives here and both call it.

Keeping it in one place matters beyond saving code: the interaction is the
thing being learned. Someone who opens a source from an answer should find the
identical control after an upload, in the same position, behaving the same way.
"""

import html

import streamlit as st

from core import rag
from core.config import Config
from core.embeddings import VectorStore
from core.models import Backend, ContextTooSmall


def ledger(sources: list[tuple[str, int]], title: str, empty_message: str) -> str:
    """
    The document column.

    Counts are passages per document. After a question they show how much of
    the answer each source carried; after an upload they show how a file was
    split, where a single passage usually means the extractor found very little.
    """
    if not sources:
        body = f'<div class="rr-ledger-empty">{empty_message}</div>'
    else:
        rows = []
        for i, (name, count) in enumerate(sources, 1):
            unit = "passage" if count == 1 else "passages"
            rows.append(
                '<div class="rr-source">'
                f'<span class="rr-source-n">{i}</span>'
                '<div class="rr-source-body">'
                f'<div class="rr-source-name">{html.escape(name)}</div>'
                f'<div class="rr-source-count">{count} {unit}</div>'
                "</div></div>"
            )
        body = "".join(rows)

    return ('<div class="rr-ledger">'
            f'<div class="rr-ledger-title">{html.escape(title)}</div>'
            f"{body}</div>")


def controls(
    scope: str,
    sources: list[tuple[str, int]],
    cfg: Config,
    store: VectorStore,
    backend: Backend,
    collection: str,
    model: str,
) -> None:
    """
    The picker and its two actions, rendered under a ledger.

    Writes what it produces into session state. The caller renders the result
    wherever it belongs on the page, which is the other column.

    Scope keys the state, so Ask and Upload do not overwrite each other and
    switching between them leaves what was open in each intact.
    """
    if not sources:
        return

    st.markdown('<div class="rr-eyebrow">Open one</div>', unsafe_allow_html=True)
    names = [name for name, _ in sources]
    picked = st.selectbox(
        "Document", names, key=f"pick::{scope}::{collection}",
        label_visibility="collapsed",
    )

    if st.button("Summarise it", use_container_width=True,
                 key=f"sum::{scope}::{collection}"):
        with st.spinner(f"Reading {picked}…"):
            try:
                st.session_state[f"opened_summary::{scope}::{collection}"] = (
                    rag.summarize(store, backend, collection, picked, model=model)
                )
            except ContextTooSmall as e:
                st.session_state[f"opened_error::{scope}::{collection}"] = str(e)
        st.session_state[f"opened::{scope}::{collection}"] = picked
        st.session_state.pop(f"opened_answer::{scope}::{collection}", None)

    question = st.text_input(
        "Ask about it", key=f"about::{scope}::{collection}",
        placeholder="Ask about this document",
        label_visibility="collapsed",
    )
    if question and st.button("Ask", use_container_width=True,
                              key=f"askbtn::{scope}::{collection}"):
        with st.spinner(f"Searching {picked}…"):
            try:
                text, results = rag.answer(
                    store, backend, collection, question, model=model,
                    top_k=cfg.get("retrieval.top_k", 15),
                    where={"source": picked},
                )
                st.session_state[f"opened_answer::{scope}::{collection}"] = {
                    "answer": text, "results": results, "question": question,
                }
            except ContextTooSmall as e:
                st.session_state[f"opened_error::{scope}::{collection}"] = str(e)
        st.session_state[f"opened::{scope}::{collection}"] = picked
        st.session_state.pop(f"opened_summary::{scope}::{collection}", None)


def result(scope: str, collection: str) -> None:
    """Render whatever was opened. Nothing if nothing has been."""
    opened = st.session_state.get(f"opened::{scope}::{collection}")
    summary = st.session_state.get(f"opened_summary::{scope}::{collection}")
    answer = st.session_state.get(f"opened_answer::{scope}::{collection}")
    error = st.session_state.get(f"opened_error::{scope}::{collection}")

    if error:
        st.error(error)
        st.session_state.pop(f"opened_error::{scope}::{collection}", None)
        return

    if not opened or not (summary or answer):
        return

    st.divider()
    st.markdown(f'<div class="rr-eyebrow">{html.escape(opened)}</div>',
                unsafe_allow_html=True)

    if summary:
        st.write(summary)

    if answer:
        if answer.get("question"):
            st.caption(answer["question"])
        st.write(answer["answer"])
        with st.expander("Passages from this document"):
            docs = answer["results"]["documents"][0]
            metas = answer["results"]["metadatas"][0]
            for i, (doc, meta) in enumerate(zip(docs, metas), 1):
                position = meta.get("chunk_index", "?")
                st.markdown(
                    f'<div class="rr-eyebrow">{i} &middot; passage {position}</div>',
                    unsafe_allow_html=True,
                )
                st.text(doc[:700] + ("…" if len(doc) > 700 else ""))


def clear(scope: str, collection: str) -> None:
    """
    Forget what was open.

    Called when the list underneath changes — a new question, a new batch of
    uploads. Without it a summary stays on screen under a list it no longer
    belongs to, with nothing saying so.
    """
    for key in ("opened", "opened_summary", "opened_answer", "opened_error"):
        st.session_state.pop(f"{key}::{scope}::{collection}", None)
