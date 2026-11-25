#!/usr/bin/env bash
# Assemble le moteur local (backend + IA + migrations + interface compilée + guides) pour l'application de bureau.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/desktop/build/backend"
echo "→ Compilation de l'interface…"
(cd "$ROOT/web/frontend" && npm ci --no-audit --no-fund >/dev/null && npm run build >/dev/null)
rm -rf "$OUT" && mkdir -p "$OUT/web/backend" "$OUT/web/frontend" "$OUT/database" "$OUT/docs"
cp -r "$ROOT/web/backend/app" "$OUT/web/backend/"
cp "$ROOT/web/backend/requirements"*.txt "$OUT/web/backend/"
cp -r "$ROOT/ai" "$OUT/"
cp -r "$ROOT/database/migrations" "$ROOT/database/seeds" "$ROOT/database/alembic.ini" "$OUT/database/"
cp -r "$ROOT/web/frontend/dist" "$OUT/web/frontend/"
mkdir -p "$OUT/scripts/install" && cp "$ROOT/scripts/install/reset_admin_password.py" "$ROOT/scripts/install/reinitialiser_mot_de_passe.bat" "$OUT/scripts/install/"
cp "$ROOT"/docs/*.pdf "$OUT/docs/" 2>/dev/null || echo "  (guides PDF non encore générés)"
find "$OUT" -name "__pycache__" -type d -prune -exec rm -rf {} +
echo "✓ Moteur assemblé : $OUT ($(du -sh "$OUT" | cut -f1))"
