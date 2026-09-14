# Rayar RAG — NiceGUI frontend

This bundle is **additive**. It does not overwrite the current Streamlit `app.py`
or `ui/` directory. It reuses the existing Rayar backend and adds:

- `nicegui_app.py`
- `ui_ng/` — NiceGUI-only presentation layer
- `core/app_lock.py` — shared OS process lock

The backend remains the current `core.config`, `core.models`, `core.embeddings`,
`core.rag`, `core.ingest`, `core.database`, and `core.auth`.

## 1. Install / update NiceGUI

From the Rayar project root:

```bash
cd ~/rayar-rag-oss
source venv/bin/activate
pip install -U "nicegui>=3.10.0"
```

## 2. Verify Streamlit/NiceGUI are stopped

```bash
ps aux | grep -E 'streamlit|nicegui' | grep -v grep
ss -ltnp | grep -E ':8501'
```

Both commands should return no Rayar frontend before you start the new one.

## 3. Copy this bundle into Rayar

Copy `nicegui_app.py`, `ui_ng/`, and `core/app_lock.py` into the existing
project root, preserving the directories.

Before starting, verify `config.yaml -> storage.chroma_dir` points to the
Chroma database you actually intend to use.

## 4. Set a persistent NiceGUI storage secret

Generate once and keep it in your shell/service environment:

```bash
export RAYAR_NICEGUI_STORAGE_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

If this changes every launch, browser session/theme storage will not remain
stable.

## 5. Start the only frontend

```bash
python nicegui_app.py
```

Open:

```text
http://SERVER-IP:8501
```

## What is migrated

- native Rayar / Executive / Slate / Midnight / Terminal themes
- collection selector
- model selector
- sign in / sign out shell (delegates password validation to `core.auth`)
- Ask
- document-level citation numbers
- retrieved excerpts
- source ledger
- source summary
- source-specific Q&A
- Upload / ingest
- create a collection when permitted
- duplicate skip / explicit replace
- post-upload source ledger and drill-down
- per-browser theme/session persistence
- single-process lock before Chroma opens

## Chroma safety

`nicegui_app.py` acquires `.rayar-rag.lock` **before** constructing the
`VectorStore`, and it also refuses to start when the old configured Streamlit
port is accepting connections.

The bundle includes `run-nightly-watch-safe.sh`, which runs your existing
`nightly-watch.sh` under the **same Linux flock** used by the NiceGUI process.
Change the scheduler/cron entry to call the safe wrapper instead of calling
`nightly-watch.sh` directly. If Rayar is active, the nightly job is skipped
rather than touching Chroma concurrently.

For manual watcher runs, use the same rule:

```bash
flock -n .rayar-rag.lock python watch.py
```

The bundle also includes `run-streamlit-safe.sh` for rollback. Once you adopt
this lock convention, use that wrapper instead of `streamlit run app.py`
directly so Streamlit also participates in the one-process rule.

## Authentication adapter

The current `core/auth.py` source was not part of the files supplied for this
migration, so the frontend deliberately does **not** recreate password hashing.
`ui_ng/auth_bridge.py` calls your existing `core.auth` implementation and
recognizes common entry-point names (`authenticate`, `authenticate_user`,
`verify_user`, `login`) plus `create_user` for first run.

If your installed `core.auth` uses a different public function name, the login
screen will report the available callable names instead of guessing. In that
case, provide `core/auth.py` and the adapter can be matched exactly without
changing any stored passwords.

## Rollback

Stop NiceGUI with `Ctrl+C`. The existing Streamlit files were not modified.
Do not launch Streamlit until the NiceGUI process has exited and released the
shared lock / Chroma access.


## Canonical port

The NiceGUI frontend now uses `app.port` from `config.yaml` by default. With the current configuration, Rayar owns port `8501`.
