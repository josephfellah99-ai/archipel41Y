#!/usr/bin/env bash
# Construit l'installateur Windows (NSIS) et la version portable d'Archipel41.
#   ./scripts/build/build_desktop.sh
# Résultats : desktop/build/dist/Archipel41-Setup-<version>-x64.exe et Archipel41-Portable-<version>-x64.exe
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[ -d "$ROOT/desktop/build/python-win" ] || "$ROOT/scripts/build/prepare_python_win.sh"
[ -d "$ROOT/desktop/build/tesseract-win" ] || "$ROOT/scripts/build/prepare_tesseract_win.sh"
"$ROOT/scripts/build/stage_backend.sh"
cd "$ROOT/desktop/electron"
npm ci --no-audit --no-fund >/dev/null
node "$ROOT/scripts/build/patch_electron_builder.cjs"
if [ "$(uname -s)" = "Linux" ]; then export A41_NO_WINE=1; fi
npx electron-builder --win --x64 --publish never
cd "$ROOT/desktop/build/dist" && sha256sum *.exe > SHA256SUMS.txt && cat SHA256SUMS.txt
