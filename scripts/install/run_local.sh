#!/usr/bin/env bash
# Lancement de la version web sur un poste (développement ou petit réseau local), base SQLite.
#   ./scripts/install/run_local.sh            → http://127.0.0.1:8041
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r web/backend/requirements-server.txt
[ -d web/frontend/dist ] || (cd web/frontend && npm ci && npm run build)
cd web/backend && exec ../../.venv/bin/python -m app
