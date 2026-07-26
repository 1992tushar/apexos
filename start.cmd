@echo off
REM One command to start / restart ApexOS (single process: UI + API on SQLite).
REM Double-click this file, or run: start.cmd
REM First run bootstraps the virtualenv, deps and demo data automatically.
REM Want a Desktop icon? Run Create-Desktop-Shortcut.cmd once.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
