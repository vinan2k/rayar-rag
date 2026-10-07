#!/usr/bin/env bash
# Optional rollback launcher. Do not use `streamlit run app.py` directly once
# adopting the shared Rayar lock convention.
set -euo pipefail
cd "$(dirname "$0")"

exec flock -n .rayar-rag.lock streamlit run app.py
