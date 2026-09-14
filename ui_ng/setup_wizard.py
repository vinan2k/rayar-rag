"""NiceGUI first-run setup wizard for Rayar RAG.

The wizard is intentionally shown only while config.yaml is absent. Nothing is
written until the Review step is finished.

It preserves the existing GitHub setup flow:
  Before you start -> AI backend/models -> Storage -> Admin -> Appearance -> Review
"""

from __future__ import annotations

import importlib
import platform
import sys
from pathlib import Path
from typing import Callable

from nicegui import app, run, ui

from core import auth, database, preflight
from core.config import CONFIG_PATH, create_default
from core.models import create as create_backend
from ui_ng import themes


def _system_label() -> str:
    fn = getattr(preflight, 'system_label', None)
    if callable(fn):
        try:
            return str(fn())
        except Exception:
            pass
    return f'{platform.system()} {platform.release()} · Python {platform.python_version()}'


def _package_check() -> tuple[list[str], list[str]]:
    """Small UI-safe package gate; core.preflight remains the source for OS advice."""
    required = {
        'yaml': 'PyYAML',
        'chromadb': 'chromadb',
        'nicegui': 'nicegui',
    }
    missing, ready = [], []
    for module, label in required.items():
        try:
            importlib.import_module(module)
            ready.append(label)
        except Exception:
            missing.append(label)
    return missing, ready


def _password_problems(password: str, confirm: str) -> list[str]:
    problems = []
    if len(password) < 8:
        problems.append('Use at least 8 characters.')
    if password != confirm:
        problems.append('The passwords do not match.')
    return problems


def _create_admin(username: str, password: str) -> None:
    """Delegate account creation to the project's existing auth module."""
    attempts = (
        lambda: auth.create_user(
            username, password, role='admin',
            collections=['*'], can_create_kb=True
        ),
        lambda: auth.create_user(username, password, 'admin', ['*'], True),
        lambda: auth.create_user(username, password),
    )
    last = None
    for attempt in attempts:
        try:
            attempt()
            return
        except TypeError as exc:
            last = exc
    raise RuntimeError(f'core.auth.create_user signature was not recognized: {last}')


class SetupWizard:
    STEPS = [
        'Before you start',
        'AI backend & models',
        'Storage',
        'Administrator',
        'Appearance',
        'Review',
    ]

    def __init__(self, *, on_complete: Callable[[], None], preview: bool = False):
        self.on_complete = on_complete
        self.preview = preview
        self.step = 0
        cfg = create_default()
        self.state = {
            'backend_type': cfg.get('backend.type', 'ollama'),
            'backend_url': cfg.get('backend.url', 'http://localhost:11434'),
            'api_key': cfg.get('backend.api_key', ''),
            'keep_alive': cfg.get('backend.keep_alive', '5m'),
            'num_ctx': cfg.get('backend.num_ctx') or '',
            'chat_model': cfg.get('backend.chat_model', ''),
            'embed_model': cfg.get('backend.embed_model', 'nomic-embed-text'),
            'chroma_dir': cfg.get('storage.chroma_dir', './chroma_db'),
            'ingested_dir': cfg.get('storage.ingested_files', './ingested_files'),
            'backup_dir': cfg.get('storage.backup_path', ''),
            'username': 'admin',
            'password': '',
            'app_name': cfg.get('app.name', 'Rayar RAG'),
            'theme': 'rayar',
        }
        self.backend_models: list[str] = []
        self.chat_models: list[str] = []
        self.embed_models: list[str] = []
        self.content = ui.element('div').classes('w-full')
        self.render()

    def _top(self):
        ui.html(
            '<div class="rr-eyebrow">First run</div>'
            '<div style="font-family:var(--rr-heading-font);font-size:2rem;'
            'margin-bottom:8px">Set up Rayar RAG</div>'
        )
        ui.label(
            'READ-ONLY PREVIEW — nothing on this page can be saved.'
            if self.preview
            else (
                'This appears only on a fresh GitHub installation. '
                'Nothing is written until the final Review step.'
            )
        ).classes('text-sm opacity-70 mb-4')

        with ui.row().classes('w-full gap-2 mb-6'):
            for i, title in enumerate(self.STEPS):
                active = i == self.step
                done = i < self.step
                mark = '✓' if done else str(i + 1)
                cls = (
                    'px-3 py-2 border text-xs '
                    + ('font-bold ' if active else 'opacity-60 ')
                )
                ui.label(f'{mark}  {title}').classes(cls).style(
                    'border-color:var(--rr-border);'
                    + ('background:var(--rr-surface2);' if active else '')
                )

    def _nav(self, *, can_next: bool = True, next_label: str = 'Continue'):
        with ui.row().classes('w-full justify-between mt-6'):
            back = ui.button('Back', icon='arrow_back').props('flat color=primary')
            back.set_visibility(self.step > 0)

            def go_back():
                if self.step > 0:
                    self.step -= 1
                    self.render()

            def go_next():
                if can_next and self.step < len(self.STEPS) - 1:
                    self.step += 1
                    self.render()

            back.on_click(go_back)
            nxt = ui.button(next_label, icon='arrow_forward') \
                .props('unelevated color=primary')
            nxt.set_enabled(can_next)
            nxt.on_click(go_next)
        return nxt

    def render(self):
        self.content.clear()
        with self.content:
            self._top()
            with ui.card().classes('w-full p-6'):
                if self.step == 0:
                    self._before_start()
                elif self.step == 1:
                    self._backend()
                elif self.step == 2:
                    self._storage()
                elif self.step == 3:
                    self._admin()
                elif self.step == 4:
                    self._appearance()
                else:
                    self._review()

    def _before_start(self):
        ui.html('<div class="rr-eyebrow">Before you start</div>')
        ui.label('Rayar checks the machine before asking you to configure AI.')
        ui.label(f'Detected: {_system_label()}').classes('text-sm opacity-70 mt-2')

        missing, ready = _package_check()
        with ui.column().classes('w-full mt-4 gap-1'):
            for name in ready:
                ui.label(f'✓ {name}').classes('text-positive text-sm')
            for name in missing:
                ui.label(f'✕ {name}').classes('text-negative text-sm')

        if missing:
            ui.label('Fix the packages before continuing.').classes(
                'font-medium mt-4'
            )
            ui.code('pip install -r requirements.txt').classes('w-full')
        else:
            ui.label('The core Python packages are available.').classes(
                'text-positive mt-4'
            )
        self._nav(can_next=not missing)

    def _backend(self):
        ui.html('<div class="rr-eyebrow">AI backend & models</div>')
        ui.label(
            'Choose the inference server Rayar should use, test it, '
            'and select the chat and embedding models.'
        ).classes('mb-4')

        backend_type = ui.radio(
            {'ollama': 'Ollama', 'openai-compatible': 'OpenAI-compatible'},
            value=self.state['backend_type'],
        ).props('inline')

        url = ui.input('Backend URL', value=self.state['backend_url']) \
            .classes('w-full mt-2').props('outlined')
        api_key = ui.input(
            'API key', value=self.state['api_key'], password=True,
            password_toggle_button=True
        ).classes('w-full').props('outlined')
        api_key.set_visibility(self.state['backend_type'] == 'openai-compatible')

        with ui.row().classes('w-full gap-3'):
            keep_alive = ui.input(
                'Keep alive', value=self.state['keep_alive']
            ).classes('grow').props('outlined dense')
            num_ctx = ui.input(
                'Context window override', value=str(self.state['num_ctx'] or '')
            ).classes('grow').props('outlined dense')

        connection = ui.label('Not checked yet.').classes('text-sm opacity-70 mt-2')
        model_area = ui.element('div').classes('w-full mt-3')
        state_ready = {'value': False}

        def backend_kind_changed():
            self.state['backend_type'] = backend_type.value
            api_key.set_visibility(backend_type.value == 'openai-compatible')
            if backend_type.value == 'ollama' and (
                not url.value or '11434' not in url.value
            ):
                url.value = 'http://localhost:11434'
            elif backend_type.value == 'openai-compatible' and (
                not url.value or '11434' in url.value
            ):
                url.value = 'http://localhost:1234/v1'
            url.update()

        backend_type.on_value_change(lambda _: backend_kind_changed())

        async def check_backend():
            self.state.update({
                'backend_type': backend_type.value,
                'backend_url': (url.value or '').strip(),
                'api_key': api_key.value or '',
                'keep_alive': (keep_alive.value or '5m').strip(),
                'num_ctx': (num_ctx.value or '').strip(),
            })
            test_cfg = create_default()
            test_cfg.set('backend.type', self.state['backend_type'])
            test_cfg.set('backend.url', self.state['backend_url'])
            test_cfg.set('backend.api_key', self.state['api_key'])
            test_cfg.set('backend.keep_alive', self.state['keep_alive'])
            try:
                ctx = int(self.state['num_ctx']) if self.state['num_ctx'] else None
            except ValueError:
                connection.set_text('Context window must be an integer or blank.')
                connection.classes('text-negative', remove='opacity-70 text-positive')
                state_ready['value'] = False
                return
            test_cfg.set('backend.num_ctx', ctx)

            connection.set_text('Checking backend…')
            try:
                candidate = create_backend(test_cfg)
                reachable = await run.io_bound(candidate.is_reachable)
                if not reachable:
                    raise RuntimeError('The backend did not answer.')
                all_models = await run.io_bound(candidate.all_models)
                chats = await run.io_bound(candidate.chat_models)
                embeds = await run.io_bound(candidate.embed_models)

                self.backend_models = all_models
                self.chat_models = chats
                self.embed_models = embeds
                connection.set_text(
                    f'Connected. {len(all_models)} model(s) reported.'
                )
                connection.classes('text-positive', remove='text-negative opacity-70')
                state_ready['value'] = bool(chats and embeds)
                render_models()
            except Exception as exc:
                state_ready['value'] = False
                connection.set_text(f'Could not connect: {exc}')
                connection.classes('text-negative', remove='text-positive opacity-70')
                render_models()

        def render_models():
            model_area.clear()
            with model_area:
                if not self.backend_models:
                    if self.state['backend_type'] == 'ollama':
                        ui.label(
                            'If Ollama is installed but no models are present, pull one '
                            'chat model and one embedding model.'
                        ).classes('text-sm')
                        ui.code(
                            'ollama pull qwen3:8b\n'
                            'ollama pull nomic-embed-text'
                        ).classes('w-full')
                    return

                chats = self.chat_models or self.backend_models
                embeds = self.embed_models
                if not embeds:
                    ui.label(
                        'No embedding model could be identified. '
                        'For OpenAI-compatible servers, model names may not reveal '
                        'their role; confirm the embedding model manually below.'
                    ).classes('text-warning text-sm')

                current_chat = (
                    self.state['chat_model']
                    if self.state['chat_model'] in chats
                    else (chats[0] if chats else '')
                )
                chat = ui.select(
                    chats, value=current_chat, label='Chat model'
                ).classes('w-full').props('outlined')

                embed_options = embeds or self.backend_models
                current_embed = (
                    self.state['embed_model']
                    if self.state['embed_model'] in embed_options
                    else (embed_options[0] if embed_options else '')
                )
                embed = ui.select(
                    embed_options, value=current_embed, label='Embedding model'
                ).classes('w-full').props('outlined')

                def remember():
                    self.state['chat_model'] = chat.value
                    self.state['embed_model'] = embed.value
                    state_ready['value'] = bool(chat.value and embed.value)

                chat.on_value_change(lambda _: remember())
                embed.on_value_change(lambda _: remember())
                remember()

        ui.button('Check again', icon='refresh', on_click=check_backend) \
            .props('outline color=primary').classes('mt-2')

        with ui.row().classes('w-full justify-between mt-6'):
            ui.button(
                'Back', icon='arrow_back',
                on_click=lambda: self._goto(self.step - 1)
            ).props('flat color=primary')

            def continue_backend():
                self.state.update({
                    'backend_type': backend_type.value,
                    'backend_url': (url.value or '').strip(),
                    'api_key': api_key.value or '',
                    'keep_alive': (keep_alive.value or '5m').strip(),
                    'num_ctx': (num_ctx.value or '').strip(),
                })
                if not state_ready['value']:
                    ui.notify(
                        'Connect successfully and choose both models first.',
                        type='warning'
                    )
                    return
                self._goto(self.step + 1)

            ui.button(
                'Continue', icon='arrow_forward',
                on_click=continue_backend
            ).props('unelevated color=primary')

    def _goto(self, step: int):
        self.step = max(0, min(step, len(self.STEPS)-1))
        self.render()

    def _storage(self):
        ui.html('<div class="rr-eyebrow">Where things are kept</div>')
        ui.label(
            'Choose where the vector database, retained originals, and optional '
            'second copy will live.'
        ).classes('mb-4')

        chroma = ui.input(
            'Chroma database', value=self.state['chroma_dir']
        ).classes('w-full').props('outlined')
        ingested = ui.input(
            'Retained originals', value=self.state['ingested_dir']
        ).classes('w-full').props('outlined')
        backup = ui.input(
            'Optional backup path', value=self.state['backup_dir']
        ).classes('w-full').props('outlined')

        ui.label(
            'The embedding model chosen above becomes part of the collection '
            'invariant: querying later with a different embedder can break retrieval.'
        ).classes('text-sm opacity-70')

        def cont():
            vals = [
                (chroma.value or '').strip(),
                (ingested.value or '').strip(),
            ]
            if not all(vals):
                ui.notify(
                    'Chroma and retained-original paths are required.',
                    type='warning'
                )
                return
            self.state['chroma_dir'] = vals[0]
            self.state['ingested_dir'] = vals[1]
            self.state['backup_dir'] = (backup.value or '').strip()
            self._goto(self.step + 1)

        with ui.row().classes('w-full justify-between mt-6'):
            ui.button('Back', on_click=lambda: self._goto(self.step - 1)) \
                .props('flat color=primary')
            ui.button('Continue', on_click=cont) \
                .props('unelevated color=primary')

    def _admin(self):
        ui.html('<div class="rr-eyebrow">Your account</div>')
        ui.label(
            'Create the first administrator account. It will have full access.'
        ).classes('mb-4')

        username = ui.input(
            'Username', value=self.state['username']
        ).classes('w-full').props('outlined')
        password = ui.input(
            'Password', password=True, password_toggle_button=True
        ).classes('w-full').props('outlined')
        confirm = ui.input(
            'Confirm password', password=True, password_toggle_button=True
        ).classes('w-full').props('outlined')
        problems = ui.column().classes('w-full gap-1')

        def cont():
            issues = _password_problems(password.value or '', confirm.value or '')
            if not (username.value or '').strip():
                issues.insert(0, 'Enter a username.')
            problems.clear()
            with problems:
                for p in issues:
                    ui.label(p).classes('text-negative text-sm')
            if issues:
                return
            self.state['username'] = username.value.strip()
            self.state['password'] = password.value
            self._goto(self.step + 1)

        with ui.row().classes('w-full justify-between mt-6'):
            ui.button('Back', on_click=lambda: self._goto(self.step - 1)) \
                .props('flat color=primary')
            ui.button('Continue', on_click=cont) \
                .props('unelevated color=primary')

    def _appearance(self):
        ui.html('<div class="rr-eyebrow">Appearance</div>')
        ui.label('All of this can be changed later.').classes('mb-4')
        name = ui.input(
            'Name', value=self.state['app_name']
        ).classes('w-full').props('outlined')
        theme = ui.radio(
            {k: v['label'] for k, v in themes.THEMES.items()},
            value=self.state['theme']
        ).props('inline')

        def cont():
            self.state['app_name'] = (name.value or 'Rayar RAG').strip()
            self.state['theme'] = theme.value or 'rayar'
            app.storage.user['theme'] = self.state['theme']
            self._goto(self.step + 1)

        with ui.row().classes('w-full justify-between mt-6'):
            ui.button('Back', on_click=lambda: self._goto(self.step - 1)) \
                .props('flat color=primary')
            ui.button('Continue', on_click=cont) \
                .props('unelevated color=primary')

    def _review(self):
        ui.html('<div class="rr-eyebrow">Review</div>')
        ui.label(
            'Nothing has been written yet. Check this, then finish.'
        ).classes('mb-4')

        s = self.state
        with ui.column().classes('w-full gap-2'):
            for label, value in (
                ('Backend', s['backend_type']),
                ('Backend URL', s['backend_url']),
                ('Chat model', s['chat_model']),
                ('Embedding model', s['embed_model']),
                ('Context override', s['num_ctx'] or 'model default'),
                ('Chroma database', s['chroma_dir']),
                ('Retained originals', s['ingested_dir']),
                ('Backup', s['backup_dir'] or 'not configured'),
                ('Administrator', s['username']),
                ('Application name', s['app_name']),
                ('Theme', themes.THEMES.get(s['theme'], {}).get('label', s['theme'])),
            ):
                with ui.row().classes('w-full justify-between border-b pb-1'):
                    ui.label(label).classes('text-sm opacity-70')
                    ui.label(str(value)).classes('text-sm font-medium')

        async def finish():
            finish_btn.disable()
            try:
                cfg = create_default()
                cfg.set('app.name', s['app_name'])
                cfg.set('app.port', 8501)
                cfg.set('app.host', '0.0.0.0')

                cfg.set('backend.type', s['backend_type'])
                cfg.set('backend.url', s['backend_url'])
                cfg.set('backend.api_key', s['api_key'])
                cfg.set('backend.chat_model', s['chat_model'])
                cfg.set('backend.embed_model', s['embed_model'])
                cfg.set('backend.keep_alive', s['keep_alive'])
                try:
                    ctx = int(s['num_ctx']) if s['num_ctx'] else None
                except ValueError:
                    raise RuntimeError('Context window must be an integer or blank.')
                cfg.set('backend.num_ctx', ctx)

                # Keep legacy Ollama fields synchronized for older code paths.
                if s['backend_type'] == 'ollama':
                    cfg.set('ollama.url', s['backend_url'])
                    cfg.set('ollama.default_model', s['chat_model'])
                    cfg.set('ollama.embed_model', s['embed_model'])
                    cfg.set('ollama.keep_alive', s['keep_alive'])

                cfg.set('storage.chroma_dir', s['chroma_dir'])
                cfg.set('storage.ingested_files', s['ingested_dir'])
                cfg.set('storage.backup_path', s['backup_dir'])

                p = themes.THEMES.get(s['theme'], themes.THEMES['rayar'])
                cfg.set('branding.primary_color', p['primary'])
                cfg.set('branding.accent_color', p['accent'])
                cfg.set('branding.background_color', p['bg'])
                cfg.set('branding.text_color', p['ink'])

                # Make storage parents now, before committing config.
                Path(s['chroma_dir']).expanduser().mkdir(parents=True, exist_ok=True)
                Path(s['ingested_dir']).expanduser().mkdir(parents=True, exist_ok=True)
                if s['backup_dir']:
                    Path(s['backup_dir']).expanduser().mkdir(parents=True, exist_ok=True)

                # Re-test backend before writing anything.
                candidate = create_backend(cfg)
                if not await run.io_bound(candidate.is_reachable):
                    raise RuntimeError(
                        'The configured AI backend is no longer reachable. '
                        'Go back and check it again.'
                    )

                # Write config only at the finish line, matching the existing wizard.
                cfg.save(CONFIG_PATH)

                try:
                    database.init()
                    if database.user_count() == 0:
                        _create_admin(s['username'], s['password'])
                except Exception:
                    # Do not leave a completed-looking setup with no admin account.
                    CONFIG_PATH.unlink(missing_ok=True)
                    raise

                app.storage.user['theme'] = s['theme']
                ui.notify('Ready. Sign in to continue.', type='positive')
                self.on_complete()
            except Exception as exc:
                ui.notify(f'Setup could not finish: {exc}', type='negative',
                          multi_line=True)
                finish_btn.enable()

        with ui.row().classes('w-full justify-between mt-6'):
            ui.button('Back', on_click=lambda: self._goto(self.step - 1)) \
                .props('flat color=primary')
            finish_btn = ui.button(
                'Preview only' if self.preview else 'Finish',
                icon='visibility' if self.preview else 'check',
                on_click=finish,
            ).props('unelevated color=primary')
            if self.preview:
                finish_btn.disable()
