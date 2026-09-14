"""Rayar RAG — NiceGUI frontend.

Fresh GitHub install:
    acquire process lock -> show first-run wizard -> write config/admin -> app

Existing install:
    acquire process lock -> load config -> initialize backend/Chroma -> app

The AI backend and ChromaDB are deliberately initialized lazily, only after
config.yaml exists.
"""

from __future__ import annotations

import html
import os
import time

from nicegui import app, ui

from core import database
from core.app_lock import AlreadyRunning, acquire as acquire_app_lock
from core.config import (
    create_default,
    exists as config_exists,
    load as load_config,
)
from core.embeddings import VectorStore
from core.models import create as create_backend
from ui_ng import themes
from ui_ng.ask import AskView
from ui_ng.auth_bridge import (
    AuthAPIError,
    allowed_collections,
    authenticate,
    create_first_user,
    normalize_user,
)
from ui_ng.setup_wizard import SetupWizard
from ui_ng.upload import UploadView


# The process guard comes first. It does not open ChromaDB.
try:
    acquire_app_lock(".rayar-rag.lock", refuse_port=None)
except AlreadyRunning as exc:
    raise SystemExit(f"\nRayar RAG refused to start:\n{exc}\n") from None


# Application services are lazy so a missing config can reach the setup wizard.
cfg = None
backend = None
store = None
APP_NAME = "Rayar RAG"


def ensure_services() -> tuple:
    global cfg, backend, store, APP_NAME

    if not config_exists():
        raise RuntimeError("Rayar setup is not complete yet.")

    if cfg is None:
        cfg = load_config()
        APP_NAME = cfg.get("app.name", "Rayar RAG")

    if backend is None:
        backend = create_backend(cfg)

    if store is None:
        embed_model = (
            cfg.get("backend.embed_model")
            or cfg.get("ollama.embed_model")
            or "nomic-embed-text"
        )
        store = VectorStore(
            cfg.get("storage.chroma_dir", "./chroma_db"),
            backend,
            embed_model,
        )

    database.init()
    return cfg, backend, store


def reset_services() -> None:
    """Used after first-run setup writes config.yaml."""
    global cfg, backend, store, APP_NAME
    cfg = None
    backend = None
    store = None
    APP_NAME = "Rayar RAG"


def _session_user() -> dict | None:
    raw = app.storage.user.get("user")
    expires = float(app.storage.user.get("user_expires", 0) or 0)
    if not raw or (expires and time.time() > expires):
        app.storage.user.pop("user", None)
        app.storage.user.pop("user_expires", None)
        return None
    return normalize_user(raw)


def _save_session(user: dict) -> None:
    local_cfg, _, _ = ensure_services()
    days = int(local_cfg.get("auth.session_days", 30))
    app.storage.user["user"] = normalize_user(user)
    app.storage.user["user_expires"] = time.time() + days * 86400
    app.storage.user.pop("login_failures", None)
    app.storage.user.pop("login_blocked_until", None)


def _sign_out() -> None:
    for key in ("user", "user_expires"):
        app.storage.user.pop(key, None)
    ui.navigate.to("/")


def _render_login(local_cfg) -> None:
    with ui.element("div").classes("rr-shell"):
        with ui.element("div").classes("rr-masthead"):
            ui.html(f'<div class="rr-brand">{html.escape(APP_NAME)}</div>')
            ui.html('<div class="rr-subbrand">Sign in</div>')

        with ui.card().classes("w-full max-w-md mt-10 p-6"):
            username = ui.input("Username").classes("w-full").props("outlined")
            password = ui.input(
                "Password", password=True, password_toggle_button=True
            ).classes("w-full").props("outlined")
            message = ui.label("").classes("text-sm text-negative")

            async def sign_in() -> None:
                now = time.time()
                blocked_until = float(
                    app.storage.user.get("login_blocked_until", 0) or 0
                )
                if blocked_until > now:
                    remaining = max(1, int(blocked_until - now))
                    message.set_text(
                        f"Too many failed attempts. Try again in {remaining} seconds."
                    )
                    return

                if not username.value or not password.value:
                    message.set_text("Enter a username and password.")
                    return

                try:
                    user = authenticate(username.value, password.value)
                except AuthAPIError as exc:
                    message.set_text(str(exc))
                    return
                except Exception as exc:
                    message.set_text(f"Sign-in failed: {exc}")
                    return

                if not user:
                    failures = int(
                        app.storage.user.get("login_failures", 0) or 0
                    ) + 1
                    max_attempts = int(
                        local_cfg.get("auth.max_login_attempts", 5)
                    )
                    app.storage.user["login_failures"] = failures
                    if failures >= max_attempts:
                        lockout = int(
                            local_cfg.get("auth.lockout_seconds", 60)
                        )
                        app.storage.user["login_blocked_until"] = now + lockout
                        app.storage.user["login_failures"] = 0
                        message.set_text(
                            f"Too many failed attempts. Try again in "
                            f"{lockout} seconds."
                        )
                    else:
                        message.set_text(
                            "That username and password do not match an account."
                        )
                    return

                _save_session(user)
                ui.navigate.to("/")

            ui.button("Sign in", on_click=sign_in) \
                .classes("w-full mt-2").props("unelevated color=primary")
            password.on("keydown.enter", sign_in)


def _render_first_user_fallback() -> None:
    """Recovery path for a config that exists without any user records."""
    with ui.element("div").classes("rr-shell"):
        with ui.element("div").classes("rr-masthead"):
            ui.html(f'<div class="rr-brand">{html.escape(APP_NAME)}</div>')
            ui.html('<div class="rr-subbrand">Administrator recovery</div>')

        with ui.card().classes("w-full max-w-md mt-10 p-6"):
            ui.label(
                "Configuration exists, but there is no administrator account. "
                "Create one to recover this installation."
            )
            username = ui.input("Username").classes("w-full").props("outlined")
            password = ui.input(
                "Password", password=True, password_toggle_button=True
            ).classes("w-full").props("outlined")
            confirm = ui.input(
                "Confirm password", password=True, password_toggle_button=True
            ).classes("w-full").props("outlined")
            message = ui.label("").classes("text-sm text-negative")

            def create() -> None:
                if not username.value or not password.value:
                    message.set_text("Enter a username and password.")
                    return
                if password.value != confirm.value:
                    message.set_text("The passwords do not match.")
                    return
                if len(password.value) < 8:
                    message.set_text("Use at least 8 characters.")
                    return
                try:
                    create_first_user(username.value, password.value)
                    ui.notify(
                        "Administrator created. Sign in to continue.",
                        type="positive",
                    )
                    ui.navigate.to("/")
                except Exception as exc:
                    message.set_text(str(exc))

            ui.button("Create administrator", on_click=create) \
                .classes("w-full mt-2").props("unelevated color=primary")



@ui.page("/setup-preview")
def setup_preview() -> None:
    """Read-only preview of the first-run installer for existing installs."""
    themes.install_css()
    dark_mode = ui.dark_mode(False)

    saved_theme = app.storage.user.get("theme", "rayar")
    if saved_theme not in themes.THEMES:
        saved_theme = "rayar"
    themes.apply(saved_theme, dark_mode)

    with ui.element("div").classes("rr-shell"):
        with ui.element("div").classes("rr-masthead"):
            ui.html('<div class="rr-brand">Rayar RAG</div>')
            ui.html('<div class="rr-subbrand">First-run setup · read-only preview</div>')

        ui.html(
            '<div class="rr-alert mt-6">'
            'Preview mode only. This route does not write config.yaml, '
            'create users, initialize ChromaDB, or change backend settings.'
            '</div>'
        )

        SetupWizard(on_complete=lambda: None, preview=True)


@ui.page("/")
def index() -> None:
    themes.install_css()
    dark_mode = ui.dark_mode(False)

    saved_theme = app.storage.user.get("theme", "rayar")
    if saved_theme not in themes.THEMES:
        saved_theme = "rayar"
    themes.apply(saved_theme, dark_mode)

    # Fresh GitHub checkout: the wizard is reachable BEFORE backend/Chroma init.
    if not config_exists():
        with ui.element("div").classes("rr-shell"):
            with ui.element("div").classes("rr-masthead"):
                ui.html('<div class="rr-brand">Rayar RAG</div>')
                ui.html('<div class="rr-subbrand">First-run setup</div>')

            def completed() -> None:
                reset_services()
                # New page request will initialize services from the saved config.
                ui.navigate.to("/")

            SetupWizard(on_complete=completed)
        return

    try:
        local_cfg, local_backend, local_store = ensure_services()
    except Exception as exc:
        with ui.element("div").classes("rr-shell"):
            with ui.element("div").classes("rr-masthead"):
                ui.html('<div class="rr-brand">Rayar RAG</div>')
            ui.html(
                '<div class="rr-alert mt-8">'
                f'Startup failed after setup: {html.escape(str(exc))}'
                '</div>'
            )
        return

    # Setup normally creates this account. This is only a recovery fallback.
    if database.user_count() == 0:
        _render_first_user_fallback()
        return

    user = _session_user()
    if not user:
        _render_login(local_cfg)
        return

    if not user.get("ai_enabled", True):
        with ui.element("div").classes("rr-shell"):
            with ui.element("div").classes("rr-masthead"):
                ui.html(f'<div class="rr-brand">{html.escape(APP_NAME)}</div>')
            ui.html(
                '<div class="rr-alert mt-8">'
                'AI access is disabled for this account.'
                '</div>'
            )
            ui.button("Sign out", on_click=_sign_out).props(
                "outline color=primary"
            )
        return

    all_collections = local_store.list_collections()
    collections = allowed_collections(user, all_collections)
    models = local_backend.chat_models()

    configured_model = (
        local_cfg.get("backend.chat_model")
        or local_cfg.get("ollama.default_model")
        or ""
    )
    state = {
        "collection": collections[0] if collections else None,
        "model": (
            configured_model if configured_model in models
            else (models[0] if models else None)
        ),
    }

    with ui.element("div").classes("rr-shell"):
        with ui.element("header").classes("rr-masthead"):
            with ui.row().classes(
                "w-full items-end justify-between gap-6"
            ):
                with ui.column().classes("gap-0"):
                    ui.html(
                        f'<div class="rr-brand">'
                        f'{html.escape(APP_NAME)}</div>'
                    )
                    ui.html(
                        '<div class="rr-subbrand">'
                        'Grounded document intelligence</div>'
                    )
                ui.label(
                    f"{user.get('username', 'user')} · "
                    f"{user.get('role', 'user')}"
                ).classes("text-sm opacity-70")

            with ui.row().classes("w-full items-center gap-4 mt-5"):
                collection_select = ui.select(
                    collections,
                    value=state["collection"],
                    label="Collection",
                ).classes("min-w-72 grow").props("outlined dense")

                model_select = ui.select(
                    models,
                    value=state["model"],
                    label="Model",
                ).classes("min-w-64").props("outlined dense")

                theme_select = ui.select(
                    {k: v["label"] for k, v in themes.THEMES.items()},
                    value=saved_theme,
                    label="Theme",
                ).classes("min-w-40").props("outlined dense")

                ui.button(
                    "Sign out", icon="logout", on_click=_sign_out
                ).props("flat color=primary")

            corpus = ui.html(
                '<div class="rr-corpus">Loading collection…</div>'
            )

        with ui.tabs().classes("w-full rr-nav") as tabs:
            ask_tab = ui.tab("Ask", icon="search")
            upload_tab = ui.tab("Upload", icon="upload")

        with ui.tab_panels(
            tabs, value=ask_tab
        ).classes("w-full bg-transparent p-0"):
            with ui.tab_panel(ask_tab).classes("p-0"):
                ask_view = AskView(
                    cfg=local_cfg,
                    store=local_store,
                    backend=local_backend,
                    get_collection=lambda: state["collection"],
                    get_model=lambda: state["model"],
                )

            with ui.tab_panel(upload_tab).classes("p-0"):
                upload_view = UploadView(
                    cfg=local_cfg,
                    store=local_store,
                    backend=local_backend,
                    get_collection=lambda: state["collection"],
                    get_model=lambda: state["model"],
                    get_user=lambda: user,
                    on_collections_changed=lambda selected:
                        refresh_collections(selected),
                )

        ui.html(
            '<div class="rr-footer">Rayar RAG · Grounded Document Intelligence</div>'
        )

    def refresh_corpus() -> None:
        name = state["collection"]
        if not name:
            corpus.set_content(
                '<div class="rr-corpus">No collection selected.</div>'
            )
            return

        try:
            count = local_store.client.get_collection(name).count()
        except Exception:
            count = 0

        matches, recorded = local_store.check_model_match(name)
        note = (
            f"<b>{html.escape(name)}</b> · "
            f"{count:,} indexed passages"
        )

        if not matches:
            note += (
                f" · ⚠ indexed with {html.escape(str(recorded))}; "
                f"configured embedding model is "
                f"{html.escape(str(local_store.embed_model))}"
            )
        elif recorded is None:
            note += (
                " · embedding model metadata unavailable "
                "(legacy collection)"
            )

        corpus.set_content(f'<div class="rr-corpus">{note}</div>')

    def refresh_collections(prefer: str | None = None) -> None:
        fresh = allowed_collections(
            user, local_store.list_collections()
        )
        collection_select.options = fresh

        if prefer in fresh:
            state["collection"] = prefer
            collection_select.value = prefer
        elif state["collection"] not in fresh:
            state["collection"] = fresh[0] if fresh else None
            collection_select.value = state["collection"]

        collection_select.update()
        upload_view.refresh_destination()
        refresh_corpus()

    def collection_changed() -> None:
        state["collection"] = collection_select.value
        ask_view.reset()
        upload_view.refresh_destination()
        refresh_corpus()

    def model_changed() -> None:
        state["model"] = model_select.value
        ask_view.reset()

    collection_select.on_value_change(
        lambda _: collection_changed()
    )
    model_select.on_value_change(
        lambda _: model_changed()
    )
    theme_select.on_value_change(
        lambda _: themes.apply(theme_select.value, dark_mode)
    )

    refresh_corpus()

    if not models:
        ui.notify(
            "No chat models were reported by the configured backend.",
            type="negative",
            multi_line=True,
        )

    if not collections:
        ui.notify(
            "No accessible collections were found. Use Upload to create one "
            "if this account is allowed to.",
            type="warning",
            multi_line=True,
        )


if __name__ in {"__main__", "__mp_main__"}:
    secret = os.getenv("RAYAR_NICEGUI_STORAGE_SECRET", "").strip()
    if not secret:
        raise SystemExit(
            "RAYAR_NICEGUI_STORAGE_SECRET is not set.\n"
            "Set it once before starting Rayar, for example:\n"
            "  export RAYAR_NICEGUI_STORAGE_SECRET=\"$(python -c "
            "'import secrets; print(secrets.token_hex(32))')\""
        )

    # The server must start even when config.yaml does not yet exist.
    # Defaults provide the first-run bind address and canonical port 8501.
    run_cfg = load_config() if config_exists() else create_default()

    ui.run(
        host=run_cfg.get("app.host", "0.0.0.0"),
        port=int(os.getenv(
            "RAYAR_NICEGUI_PORT",
            str(run_cfg.get("app.port", 8501)),
        )),
        title=run_cfg.get("app.name", "Rayar RAG"),
        reload=False,
        show=False,
        storage_secret=secret,
    )
