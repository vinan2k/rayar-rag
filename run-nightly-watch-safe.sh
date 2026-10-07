#!/usr/bin/env bash
# Run the existing nightly watcher only when no Rayar frontend/ingestion process
# holds the shared lock. Uses the same Linux flock primitive as core/app_lock.py.
set -euo pipefail
cd "$(dirname "$0")"

if flock -n .rayar-rag.lock -c './nightly-watch.sh'; then
  exit 0
fi

echo "Rayar RAG is active; nightly watch skipped to protect ChromaDB." >&2
exit 0
