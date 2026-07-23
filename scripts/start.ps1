# ApexOS — start / restart the app in one go.
# The single FastAPI process serves BOTH the web UI (Jinja) and the JSON API,
# backed by a SQLite file (self-initialized on startup) — no DB server, no web build.
# Run from a NORMAL PowerShell. Frees the port first, so this doubles as a restart.
$ErrorActionPreference = 'SilentlyContinue'

$root = Split-Path $PSScriptRoot -Parent
$api  = Join-Path $root 'apps\api'

Write-Host '== ApexOS: (re)starting ==' -ForegroundColor Cyan

# Free port 8000 (so this also works as a restart)
Get-NetTCPConnection -LocalPort 8000 -State Listen -EA SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force -EA SilentlyContinue }

# API + UI — own window, with hot reload (SQLite schema self-initializes on boot)
Start-Process powershell -ArgumentList @('-NoExit','-Command',
  "cd `"$api`"; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000")

Write-Host ''
Write-Host 'ApexOS is starting up.' -ForegroundColor Green
Write-Host '  App : http://localhost:8000/'
Write-Host '  API : http://localhost:8000/docs'
Write-Host 'Give it ~5s on first launch, then open the App URL.'
