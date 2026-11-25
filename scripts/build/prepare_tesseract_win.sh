#!/usr/bin/env bash
# Prépare Tesseract OCR 5.4 pour Windows (build UB Mannheim) avec les langues française et anglaise.
# Seuls tesseract.exe et les DLL nécessaires sont conservés. Nécessite 7z et objdump (binutils).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/desktop/build/tesseract-win"
URL="https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
FRA="${TESSDATA_FRA:-/usr/share/tesseract-ocr/5/tessdata/fra.traineddata}"   # paquet tesseract-ocr-fra (tessdata_fast, Apache 2.0)
TMP="$(mktemp -d)"
curl -fsSL -o "$TMP/setup.exe" "$URL"
7z x -y -o"$TMP/t" "$TMP/setup.exe" > /dev/null
rm -rf "$OUT" && mkdir -p "$OUT/tessdata"
cd "$TMP/t"
python3 - "$OUT" <<'PY'
import os, re, shutil, subprocess, sys
out = sys.argv[1]; need = set(); todo = ["tesseract.exe"]
while todo:
    f = todo.pop()
    for d in re.findall(r"DLL Name: (\S+)", subprocess.run(["objdump", "-p", f], capture_output=True, text=True).stdout):
        if os.path.exists(d) and d not in need:
            need.add(d); todo.append(d)
for f in ["tesseract.exe", *need]:
    shutil.copy(f, out)
print(f"  {len(need)} DLL copiées")
PY
cp -r tessdata/configs tessdata/eng.traineddata "$OUT/tessdata/"
cp "$FRA" "$OUT/tessdata/fra.traineddata"
cp doc/LICENSE "$OUT/LICENSE-tesseract.txt"
echo "✓ Tesseract Windows prêt : $OUT ($(du -sh "$OUT" | cut -f1))"
rm -rf "$TMP"
