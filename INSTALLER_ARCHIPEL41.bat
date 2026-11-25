@echo off
chcp 65001 >nul
title Archipel41 - preparation de linstallateur
cd /d "%~dp0"
echo.
echo Assemblage de linstallateur Archipel41...
if not exist "Archipel41-Setup.part0" goto manque
if not exist "Archipel41-Setup.part1" goto manque
copy /b /y "Archipel41-Setup.part0"+"Archipel41-Setup.part1" "Archipel41-Setup-1.0.0-x64.exe" >nul
echo Verification de lintegrite du fichier...
certutil -hashfile "Archipel41-Setup-1.0.0-x64.exe" SHA256 | findstr /i "5751053d09b77aed647c20768b44fc749f2759b25476ab3e8741ad7f8593af81" >nul
if errorlevel 1 goto corrompu
echo OK. Lancement de linstallation...
start "" "Archipel41-Setup-1.0.0-x64.exe"
exit /b 0
:manque
echo ERREUR : les fichiers Archipel41-Setup.part0 et Archipel41-Setup.part1 doivent etre dans ce dossier.
pause
exit /b 1
:corrompu
echo ERREUR : le fichier assemble est incomplet. Retelechargez le ZIP et recommencez.
pause
exit /b 1
