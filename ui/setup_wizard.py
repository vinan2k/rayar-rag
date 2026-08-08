"""
setup_wizard.py — First run, in steps that will not let you past a missing
prerequisite.

A list of requirements is easy to skim past. A gate is not. Each step states
what it needs, shows whether the machine currently satisfies it, and refuses to
advance until it does. The checks run live, so a person sees what is already
sorted rather than verifying each item themselves.

The order follows the dependency chain. Nothing can be configured before the
thing it depends on is present: no models without Ollama, no collections
without a writable directory, no sign-in without an account.
"""

from pathlib import Path

import streamlit as st

from core import auth, config, database, preflight, theme
from core import models
from ui.branding import css, top_gap

STEPS = [
    "Readiness",
    "Storage",
    "Account",
    "Appearance",
    "Finish",
]


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------

def _state() -> dict:
    """Wizard state, held across reruns."""
    if "wizard" not in st.session_state:
        st.session_state["wizard"] = {
            "step": 0,
            "backend_type": "ollama",
            "ollama_url": "http://localhost:11434",
            "api_key": "",
            # Left empty. The readiness step lists what the server actually
            # has and the person chooses; guessing here would preselect a
            # model that may not be installed.
            "chat_model": "",
            "embed_model": "",
            "chroma_dir": "./chroma_db",
            "ingested_dir": "./ingested_files",
            "backup_dir": "",
            "app_name": "Rayar RAG",
            "theme": "rayar",
            "username": "",
            "password": "",
        }
    return st.session_state["wizard"]


def _advance() -> None:
    _state()["step"] += 1
    st.rerun()


def _back() -> None:
    _state()["step"] = max(0, _state()["step"] - 1)
    st.rerun()


# --------------------------------------------------------------------------
# chrome
# --------------------------------------------------------------------------

def _progress(current: int) -> None:
    """Where we are in the sequence."""
    marks = []
    for i, name in enumerate(STEPS):
        if i < current:
            marks.append(f"<b>{name}</b>")
        elif i == current:
            marks.append(f'<span style="color:var(--rr-primary)"><b>{name}</b></span>')
        else:
            marks.append(f'<span style="opacity:.45">{name}</span>')
    st.markdown(
        f'<div class="rr-corpus">Step {current + 1} of {len(STEPS)} &nbsp;·&nbsp; '
        + " &nbsp;→&nbsp; ".join(marks)
        + "</div>",
        unsafe_allow_html=True,
    )


def _check_row(passed: bool, label: str, detail: str) -> None:
    """One line of the readiness table."""
    mark = "✓" if passed else "✗"
    colour = "var(--rr-primary)" if passed else "var(--st-red-color, #B3261E)"
    st.markdown(
        f'<div style="display:flex;gap:.7rem;padding:.45rem 0;'
        f'border-bottom:1px solid var(--rr-hairline)">'
        f'<span style="color:{colour};font-weight:600;width:1rem">{mark}</span>'
        f'<span style="width:9rem">{label}</span>'
        f'<span style="opacity:.7">{detail}</span></div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# step 1 — readiness
# --------------------------------------------------------------------------

def _step_readiness(w: dict) -> None:
    st.markdown('<div class="rr-eyebrow">Before you start</div>',
                unsafe_allow_html=True)
    st.write(
        "Rayar RAG runs entirely on this machine. It needs Python packages "
        "matching the tested set, Ollama running, and at least one chat model "
        "and one embedding model pulled."
    )
    st.caption(f"Detected: {preflight.system_label()}")

    kinds = {
        "Ollama": "ollama",
        "OpenAI-compatible server": "openai-compatible",
    }
    chosen = st.radio(
        "Inference server",
        list(kinds),
        index=0 if w["backend_type"] == "ollama" else 1,
        horizontal=True,
        captions=[
            "ollama.com",
            "LM Studio, llama.cpp, vLLM, LocalAI",
        ],
    )
    if kinds[chosen] != w["backend_type"]:
        w["backend_type"] = kinds[chosen]
        w["ollama_url"] = (
            "http://localhost:11434" if w["backend_type"] == "ollama"
            else "http://localhost:1234/v1"
        )

    w["ollama_url"] = st.text_input(
        "Address", value=w["ollama_url"],
        help="Leave as it is unless the server runs on another machine.",
    )
    if w["backend_type"] == "openai-compatible":
        w["api_key"] = st.text_input(
            "API key", value=w["api_key"], type="password",
            help="Most local servers ignore this. Any value will do.",
        )

    st.write("")

    # --- packages ---
    problems = preflight.dependency_problems()
    _check_row(
        not problems,
        "Packages",
        "matched to the tested set" if not problems
        else f"{len(problems)} differ from the tested set",
    )

    # --- ollama ---
    if w["backend_type"] == "openai-compatible":
        client = models.OpenAIBackend(w["ollama_url"], w["api_key"])
    else:
        client = models.OllamaBackend(w["ollama_url"])
    reachable = client.is_reachable()
    _check_row(
        reachable,
        "Ollama",
        f"reachable at {w['ollama_url']}" if reachable else "not reachable",
    )

    # --- models ---
    chat_models = client.chat_models() if reachable else []
    embed_models = client.embed_models() if reachable else []
    has_models = bool(chat_models) and bool(embed_models)
    if has_models:
        detail = f"{len(chat_models)} chat, {len(embed_models)} embedding"
    elif reachable:
        detail = "none pulled yet"
    else:
        detail = "cannot check until Ollama is reachable"
    _check_row(has_models, "Models", detail)

    st.write("")

    # --- what to do about each failure ---
    if problems:
        st.markdown('<div class="rr-eyebrow">Fix the packages</div>',
                    unsafe_allow_html=True)
        for p in problems:
            st.write(f"· {p}")
        st.code("pip install -r requirements.txt", language="bash")

    if not reachable and w["backend_type"] == "ollama":
        st.markdown('<div class="rr-eyebrow">Install Ollama</div>',
                    unsafe_allow_html=True)
        lines = preflight.install_instructions()
        st.code(lines[0], language="bash")
        for line in lines[1:]:
            st.caption(line)
    elif not reachable:
        st.caption(
            "Start the server and make sure it accepts connections from this "
            "machine. LM Studio needs: lms server start --bind 0.0.0.0"
        )

    if reachable and not has_models:
        st.markdown('<div class="rr-eyebrow">Pull two models</div>',
                    unsafe_allow_html=True)
        st.write(
            "Two are needed: one to write answers, and one to index documents."
        )
        st.code("ollama pull qwen3:8b\nollama pull nomic-embed-text",
                language="bash")
        st.caption(
            "A reasonable starting point on most machines. The README has "
            "more on choosing."
        )

    if has_models:
        w["chat_model"] = st.selectbox(
            "Model for answering questions", chat_models,
            index=chat_models.index(w["chat_model"])
            if w["chat_model"] in chat_models else 0,
        )
        if w["backend_type"] == "openai-compatible":
            st.caption(
                "This server reports model names only, so the split between "
                "chat and embedding models below is a guess from those names. "
                "Correct it if either is wrong."
            )
        w["embed_model"] = st.selectbox(
            "Model for embedding documents", embed_models,
            index=embed_models.index(w["embed_model"])
            if w["embed_model"] in embed_models else 0,
            help="This cannot be changed later without rebuilding every "
                 "collection. Retrieval fails silently if it does not match.",
        )

    ready = reachable and has_models
    left, right = st.columns([1, 1])
    with left:
        if st.button("Check again", use_container_width=True):
            st.rerun()
    with right:
        if st.button("Continue", type="primary", disabled=not ready,
                     use_container_width=True):
            _advance()

    if not ready:
        st.caption(
            "Do the steps above in a terminal, then use Check again. "
            "Nothing is written until the last step."
        )


# --------------------------------------------------------------------------
# step 2 — storage
# --------------------------------------------------------------------------

def _writable(path_str: str) -> tuple[bool, str]:
    """Can we create and write in this directory."""
    if not path_str.strip():
        return False, "empty"
    path = Path(path_str).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".rayar_write_test"
        probe.write_text("ok")
        probe.unlink()
        return True, str(path.resolve())
    except Exception as e:
        return False, str(e)


def _step_storage(w: dict) -> None:
    st.markdown('<div class="rr-eyebrow">Where things are kept</div>',
                unsafe_allow_html=True)
    st.write(
        "Documents are indexed into a local database. Original files are kept "
        "so a collection can be rebuilt without hunting for them again."
    )

    # Seeded once, then owned by session state. Passing value= on every run
    # re-seeded each field from the previous value while the check below read
    # the new one, so the path on screen and the path being validated were
    # different — a tick could appear against something the field no longer
    # showed. A key lets the widget hold its own value.
    for field in ("chroma_dir", "ingested_dir", "backup_dir"):
        st.session_state.setdefault(f"wiz_{field}", w[field])

    w["chroma_dir"] = st.text_input(
        "Index directory", key="wiz_chroma_dir",
        help="The vector database. Grows with the number of documents.",
    )
    w["ingested_dir"] = st.text_input(
        "Ingested files", key="wiz_ingested_dir",
        help="A copy of every document added through the browser.",
    )
    w["backup_dir"] = st.text_input(
        "Backup location (optional)", key="wiz_backup_dir",
        placeholder="/Volumes/NAS/documents",
        help="A second copy, on a drive or network share. Leave empty to skip.",
    )

    st.caption(
        "Each path is checked by creating a file there and removing it, so a "
        "tick means it is genuinely writable by the account running this."
    )

    st.write("")

    chroma_ok, chroma_detail = _writable(w["chroma_dir"])
    _check_row(chroma_ok, "Index", chroma_detail)

    ingest_ok, ingest_detail = _writable(w["ingested_dir"])
    _check_row(ingest_ok, "Files", ingest_detail)

    if w["backup_dir"].strip():
        backup_ok, backup_detail = _writable(w["backup_dir"])
        _check_row(backup_ok, "Backup", backup_detail)
    else:
        backup_ok = True
        _check_row(True, "Backup", "not set")

    st.write("")
    ready = chroma_ok and ingest_ok and backup_ok
    left, right = st.columns([1, 1])
    with left:
        if st.button("Back", use_container_width=True):
            _back()
    with right:
        if st.button("Continue", type="primary", disabled=not ready,
                     use_container_width=True):
            _advance()


# --------------------------------------------------------------------------
# step 3 — account
# --------------------------------------------------------------------------

def _step_account(w: dict) -> None:
    st.markdown('<div class="rr-eyebrow">Your account</div>',
                unsafe_allow_html=True)
    st.write(
        "This first account can see every collection and manage other people. "
        "Accounts are stored on this machine only."
    )

    w["username"] = st.text_input("Username", value=w["username"])
    password = st.text_input("Password", type="password")
    confirm = st.text_input("Confirm password", type="password")

    problems = []
    if not w["username"].strip():
        problems.append("Choose a username.")
    if len(password) < 8:
        problems.append("Use a password of at least 8 characters.")
    elif password != confirm:
        problems.append("The passwords do not match.")

    if password:
        for p in problems:
            st.caption(p)

    ready = not problems
    if ready:
        w["password"] = password

    st.write("")
    left, right = st.columns([1, 1])
    with left:
        if st.button("Back", use_container_width=True):
            _back()
    with right:
        if st.button("Continue", type="primary", disabled=not ready,
                     use_container_width=True):
            _advance()


# --------------------------------------------------------------------------
# step 4 — appearance
# --------------------------------------------------------------------------

def _step_appearance(w: dict) -> None:
    st.markdown('<div class="rr-eyebrow">Appearance</div>',
                unsafe_allow_html=True)
    st.write("All of this can be changed later.")

    w["app_name"] = st.text_input("Name", value=w["app_name"])

    presets = theme.available()
    if presets:
        notes = theme.descriptions()
        w["theme"] = st.radio(
            "Theme", presets,
            index=presets.index(w["theme"]) if w["theme"] in presets else 0,
            captions=[notes.get(p, "") for p in presets],
        )

    st.write("")
    left, right = st.columns([1, 1])
    with left:
        if st.button("Back", use_container_width=True):
            _back()
    with right:
        if st.button("Continue", type="primary", use_container_width=True):
            _advance()


# --------------------------------------------------------------------------
# step 5 — finish
# --------------------------------------------------------------------------

def _step_finish(w: dict) -> None:
    st.markdown('<div class="rr-eyebrow">Review</div>', unsafe_allow_html=True)
    st.write("Nothing has been written yet. Check this, then finish.")

    st.markdown(
        f"""
| | |
|---|---|
| Name | {w['app_name']} |
| Server | {w['backend_type']} at {w['ollama_url']} |
| Answering model | {w['chat_model']} |
| Embedding model | {w['embed_model']} |
| Index | {w['chroma_dir']} |
| Files | {w['ingested_dir']} |
| Backup | {w['backup_dir'] or 'not set'} |
| Theme | {w['theme']} |
| Account | {w['username']} |
"""
    )

    st.write("")
    left, right = st.columns([1, 1])
    with left:
        if st.button("Back", use_container_width=True):
            _back()
    with right:
        if st.button("Finish", type="primary", use_container_width=True):
            _write(w)


def _write(w: dict) -> None:
    """Create config.yaml, the database, and the first account."""
    try:
        cfg = config.create_default()
        cfg.set("app.name", w["app_name"])
        cfg.set("backend.type", w["backend_type"])
        cfg.set("backend.url", w["ollama_url"])
        cfg.set("backend.api_key", w["api_key"])
        cfg.set("backend.chat_model", w["chat_model"])
        cfg.set("backend.embed_model", w["embed_model"])
        cfg.set("storage.chroma_dir", w["chroma_dir"])
        cfg.set("storage.ingested_files", w["ingested_dir"])
        cfg.set("storage.backup_path", w["backup_dir"])
        cfg.save()

        theme.apply(w["theme"])

        database.init()
        auth.create_user(
            w["username"], w["password"], role="admin", can_create_kb=True
        )
    except Exception as e:
        st.error(f"Setup could not finish: {e}")
        return

    st.session_state.pop("wizard", None)
    st.success("Ready. Sign in to continue.")
    st.rerun()


# --------------------------------------------------------------------------
# entry
# --------------------------------------------------------------------------

def show() -> None:
    """Render the wizard. Called when no config.yaml exists."""
    st.markdown(css(), unsafe_allow_html=True)
    top_gap()

    w = _state()
    step = w["step"]

    st.title("Rayar RAG")
    _progress(step)

    if step == 0:
        _step_readiness(w)
    elif step == 1:
        _step_storage(w)
    elif step == 2:
        _step_account(w)
    elif step == 3:
        _step_appearance(w)
    else:
        _step_finish(w)
