"""
app.py — Rayar RAG entry point.

Routes between three states: no accounts yet, signed out, and the workspace.
Everything below the router reads from config.yaml or .streamlit/config.toml;
nothing is hardcoded.
"""

import streamlit as st

from core import auth, config, database, theme
from core.embeddings import VectorStore
from core import models
from ui import ask, login, setup_wizard, upload
from ui.branding import css, footer, masthead, top_gap


def _boot():
    """Load config and open connections."""
    cfg = config.load()
    database.init()
    backend = models.create(cfg)
    embed_model = cfg.get("backend.embed_model") or cfg.get("ollama.embed_model")
    store = VectorStore(cfg.get("storage.chroma_dir"), backend, embed_model)
    return cfg, backend, store


@st.cache_data(show_spinner=False)
def _document_count(chroma_dir: str, collection: str, chunks: int) -> tuple[int, bool]:
    """
    How many distinct documents a collection holds, and whether that is exact.

    Counting means reading the metadata of every chunk, which is slow on a
    large collection and repeats on every rerun, so the result is cached
    against the collection and its chunk count: it recomputes when documents
    are added and not otherwise.

    Above the sampling limit the figure is a floor rather than a total, and is
    reported as such instead of being quietly wrong.
    """
    import chromadb

    limit = 20_000
    try:
        client = chromadb.PersistentClient(path=chroma_dir)
        col = client.get_collection(collection)
        sample = col.get(limit=limit, include=["metadatas"])
        sources = {m.get("source") for m in sample["metadatas"] if m.get("source")}
        return len(sources), chunks <= limit
    except Exception:
        return 0, False


def _visible_collections(store: VectorStore, user: dict) -> list[str]:
    """Collections this account may see, in name order."""
    everything = sorted(store.list_collections())
    if "all" in user.get("collections", []):
        return everything
    return [c for c in everything if c in user["collections"]]


def _first_account(cfg) -> None:
    """Create the first account. It gets full access."""
    st.markdown(css(), unsafe_allow_html=True)
    top_gap()
    masthead(cfg.get("app.name", "Rayar RAG"))
    st.markdown('<div class="rr-eyebrow">First run</div>', unsafe_allow_html=True)
    st.write("Create the first account. It will have full access.")

    with st.form("first_account"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account")

    if submitted:
        if not username or not password:
            st.error("Enter a username and password.")
        elif password != confirm:
            st.error("The passwords do not match.")
        elif len(password) < 8:
            st.error("Use at least 8 characters.")
        else:
            auth.create_user(username, password, role="admin", can_create_kb=True)
            st.success("Account created. Sign in to continue.")
            st.rerun()


def _appearance() -> None:
    """
    Theme picker.

    Writes only when the person actually chooses, not on every rerun. An
    earlier version compared the radio's value against the file on each pass
    and wrote whenever they differed, which meant any edit made to
    config.toml outside the app was overwritten the next time the script ran.
    """
    presets = theme.available()
    if not presets:
        return

    current = theme.active()
    index = presets.index(current) if current in presets else 0
    notes = theme.descriptions()

    with st.popover("Appearance", use_container_width=True):
        st.markdown('<div class="rr-eyebrow">Theme</div>', unsafe_allow_html=True)
        picked = st.radio(
            "Theme",
            presets,
            index=index,
            label_visibility="collapsed",
            captions=[notes.get(p, "") for p in presets],
            key="theme_pick",
        )
        if st.button("Apply", disabled=picked == current,
                     use_container_width=True):
            if theme.apply(picked):
                st.rerun()
            else:
                st.error("Could not write .streamlit/config.toml.")
        st.caption("A change of typeface needs the server restarted.")


def main() -> None:
    st.set_page_config(page_title="Rayar RAG", page_icon="◈", layout="wide")

    if not config.exists():
        setup_wizard.show()
        st.stop()

    cfg, ollama, store = _boot()
    app_name = cfg.get("app.name", "Rayar RAG")

    if database.user_count() == 0:
        _first_account(cfg)
        st.stop()

    if "user" not in st.session_state:
        login.show(cfg)
        st.stop()

    user = st.session_state["user"]

    st.markdown(css(), unsafe_allow_html=True)
    top_gap()
    masthead(app_name, user["username"], user["role"])

    if not ollama.is_reachable():
        if st.button("Sign out"):
            login.sign_out()
        st.error(
            f"Cannot reach {ollama.name} at {ollama.url}. "
            "Start the server, or change backend.url in config.yaml."
        )
        st.stop()

    chat_models = ollama.chat_models()
    if not chat_models:
        if st.button("Sign out"):
            login.sign_out()
        st.markdown('<div class="rr-eyebrow">No models yet</div>',
                    unsafe_allow_html=True)
        st.write(
            f"{ollama.name} is reachable but has no models. Two are needed: "
            "one to write answers, and one to index documents."
        )
        st.code("ollama pull qwen3:8b\nollama pull nomic-embed-text",
                language="bash")
        st.caption(
            "Those two are a reasonable starting point on most machines. "
            "The README has more on choosing, including what to do on a "
            "computer without a graphics card."
        )
        st.stop()

    collections = _visible_collections(store, user)
    if not collections:
        # An administrator arriving here has just finished setup and has an
        # empty database. Telling them to ask an administrator would be
        # telling them to ask themselves, with no way to act on it, so they
        # get the upload form instead. Someone without that permission gets
        # the message, and a way to sign out, which an earlier version
        # withheld by calling st.stop() before the button rendered.
        if st.button("Sign out"):
            login.sign_out()

        if user.get("can_create_kb"):
            first_model = (cfg.get("backend.chat_model")
                           or cfg.get("ollama.default_model")
                           or chat_models[0])
            if first_model not in chat_models:
                first_model = chat_models[0]
            upload.show(cfg, store, ollama, "", user, first_model)
        else:
            st.markdown('<div class="rr-eyebrow">Nothing to search</div>',
                        unsafe_allow_html=True)
            st.write(
                "No collections have been shared with this account yet. "
                "Whoever administers this installation can grant access."
            )
        st.stop()

    default_model = (cfg.get("backend.chat_model")
                     or cfg.get("ollama.default_model"))
    model_index = chat_models.index(default_model) if default_model in chat_models else 0

    col_pick, col_model, col_theme, col_out = st.columns([3, 3, 1.4, 1.4], gap="medium")
    with col_pick:
        collection = st.selectbox("Collection", collections)
    with col_model:
        model = st.selectbox("Model", chat_models, index=model_index)
    with col_theme:
        st.write("")
        _appearance()
    with col_out:
        st.write("")
        if st.button("Sign out", use_container_width=True):
            login.sign_out()

    counts = store.collection_counts()
    matched, recorded = store.check_model_match(collection)
    # documents is the number a person recognises; chunks is what retrieval
    # actually searches, and the ratio tells them how finely it was split
    chunk_count = counts.get(collection, 0)
    doc_count, exact = _document_count(
        cfg.get("storage.chroma_dir"), collection, chunk_count
    )
    docs_word = "document" if doc_count == 1 else "documents"
    prefix = "" if exact else "at least "
    note = (
        f"<b>{collection}</b> &middot; {prefix}{doc_count:,} {docs_word} "
        f"&middot; {chunk_count:,} chunks"
    )
    strip_class = "rr-corpus"
    if not matched:
        note += (
            f" &middot; built with <b>{recorded}</b>, querying with "
            f"<b>{store.embed_model}</b> — results will be poor"
        )
        strip_class += " rr-corpus-warn"
    st.markdown(f'<div class="{strip_class}">{note}</div>', unsafe_allow_html=True)

    tab_ask, tab_upload = st.tabs(["Ask", "Upload"])

    with tab_ask:
        ask.show(cfg, store, ollama, collection, model, user)

    with tab_upload:
        upload.show(cfg, store, ollama, collection, user, model)

    footer()


if __name__ == "__main__":
    main()
