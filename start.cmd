@echo off
REM One command to start / restart ApexOS (single process: UI + API on SQLite). Double-click or run: start.cmd
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
