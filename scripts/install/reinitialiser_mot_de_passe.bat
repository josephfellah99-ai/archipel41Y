@echo off
REM Archipel41 (poste Windows) : réinitialiser le mot de passe d'un compte local.
REM Fermez Archipel41 avant de lancer ce script (double-clic).
chcp 65001 >nul
set "A41=%LOCALAPPDATA%\Programs\Archipel41\resources"
if not exist "%A41%\python\python.exe" set "A41=%ProgramFiles%\Archipel41\resources"
set "ARCHIPEL_MODE=desktop"
set "ARCHIPEL_DATA_DIR=%APPDATA%\Archipel41\data"
set "PYTHONPATH=%A41%\backend\web\backend;%A41%\backend"
set /p EMAIL="Adresse e-mail du compte : "
"%A41%\python\python.exe" "%A41%\backend\scripts\install\reset_admin_password.py" --email %EMAIL%
pause
