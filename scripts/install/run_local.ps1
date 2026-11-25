# Lancement de la version web sous Windows (PowerShell), base SQLite locale : http://127.0.0.1:8041
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."
Set-Location $root
if (-not (Test-Path .venv)) { py -3.12 -m venv .venv }
.\.venv\Scripts\pip install -q -r web\backend\requirements-server.txt
if (-not (Test-Path web\frontend\dist)) { Push-Location web\frontend; npm ci; npm run build; Pop-Location }
Set-Location web\backend
..\..\.venv\Scripts\python -m app
