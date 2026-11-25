#!/usr/bin/env bash
# Prépare l'interpréteur Python 3.12 pour Windows x64 (python-build-standalone) et y installe
# les dépendances du moteur local compilées pour win_amd64. Exécutable depuis Linux, macOS ou Windows (Git Bash).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/desktop/build/python-win"
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20241206/cpython-3.12.8+20241206-x86_64-pc-windows-msvc-install_only.tar.gz"
PIP="${PIP:-$ROOT/.venv/bin/pip}"
TMP="$(mktemp -d)"
echo "→ Téléchargement de Python 3.12 (Windows x64)…"
curl -fsSL -o "$TMP/python.tar.gz" "$PY_URL"
rm -rf "$OUT" && mkdir -p "$(dirname "$OUT")"
tar xzf "$TMP/python.tar.gz" -C "$TMP" && mv "$TMP/python" "$OUT"
echo "→ Installation des dépendances win_amd64…"
"$PIP" install --quiet --platform win_amd64 --python-version 3.12 --implementation cp --abi cp312 \
  --only-binary=:all: --target "$OUT/Lib/site-packages" -r "$ROOT/web/backend/requirements-desktop.txt"
echo "→ Allègement (symboles de débogage, Tk, tests)…"
cd "$OUT"
find . -name "*.pdb" -delete
rm -rf tcl include libs Scripts Lib/test Lib/idlelib Lib/tkinter Lib/turtledemo Lib/ensurepip \
       Lib/site-packages/pip Lib/site-packages/pip-* Lib/site-packages/bin DLLs/_tkinter.pyd DLLs/tcl*.dll DLLs/tk*.dll
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
if find . -name "*.so" | grep -q .; then echo "ERREUR : bibliothèque non Windows détectée" >&2; exit 1; fi
echo "✓ Python Windows prêt : $OUT ($(du -sh . | cut -f1))"
rm -rf "$TMP"
