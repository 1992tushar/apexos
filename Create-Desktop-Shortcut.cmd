@echo off
REM Puts an "ApexOS" shortcut on your Desktop pointing at THIS clone. Run once after cloning.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\create-desktop-shortcut.ps1"
pause
