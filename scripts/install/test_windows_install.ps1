# Vérifie une installation Windows d'Archipel41 : moteur Python embarqué, base SQLite, OCR Tesseract, API.
#   powershell -ExecutionPolicy Bypass -File test_windows_install.ps1
$ErrorActionPreference = "Stop"
$res = "$env:LOCALAPPDATA\Programs\Archipel41\resources"
if (-not (Test-Path "$res\python\python.exe")) { $res = "$env:ProgramFiles\Archipel41\resources" }
$data = Join-Path $env:TEMP "a41-test-$(Get-Random)"
$env:ARCHIPEL_MODE = "desktop"; $env:ARCHIPEL_DATA_DIR = $data; $env:ARCHIPEL_PORT = "18041"
$env:ARCHIPEL_FRONTEND_DIST = "$res\backend\web\frontend\dist"
$env:PYTHONPATH = "$res\backend\web\backend;$res\backend"
$env:ARCHIPEL_TESSERACT_CMD = "$res\tesseract\tesseract.exe"; $env:TESSDATA_PREFIX = "$res\tesseract\tessdata"
$p = Start-Process "$res\python\python.exe" -ArgumentList "-m","app" -WorkingDirectory "$res\backend\web\backend" -PassThru -WindowStyle Hidden
try {
  for ($i = 0; $i -lt 60; $i++) { try { Invoke-RestMethod http://127.0.0.1:18041/api/health | Out-Null; break } catch { Start-Sleep 1 } }
  $h = Invoke-RestMethod http://127.0.0.1:18041/api/health; Write-Host "Moteur : $($h.status) / $($h.mode)"
  $s = Invoke-RestMethod -Method Post -ContentType "application/json" -Uri http://127.0.0.1:18041/api/setup -Body '{"agency_name":"Test Windows","admin_email":"admin@test.fr","admin_name":"Admin","admin_password":"Test#Windows2026"}'
  $hdr = @{ Authorization = "Bearer $($s.token)" }
  $p1 = Invoke-RestMethod -Method Post -ContentType "application/json" -Headers $hdr -Uri http://127.0.0.1:18041/api/projects -Body '{"code":"W1","name":"Test"}'
  $info = Invoke-RestMethod -Headers $hdr http://127.0.0.1:18041/api/system/info
  Write-Host "OCR disponible : $($info.ocr)"; if (-not $info.ocr) { throw "OCR indisponible" }
  $scan = Get-ChildItem "$res\backend\database\seeds\demo_files\Devis_LeGoff_Lot02_scan.jpg"
  $form = @{ files = $scan; project_id = $p1.id }
  $q = Invoke-RestMethod -Method Post -Headers $hdr -Uri http://127.0.0.1:18041/api/quotes/import -Form $form
  $total = $q[0].quote.computed.total_ht; Write-Host "Devis scanné : total HT recalculé = $total"
  if ($q[0].quote.lines.Count -lt 10) { throw "Extraction OCR insuffisante" }
  Write-Host "✓ Installation Windows vérifiée"
} finally { Stop-Process $p -Force }
