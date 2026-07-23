# ApexOS — start / restart the whole stack (API + Web) in one go.
# Run from a NORMAL PowerShell. Kills any running instances first, so it's also a restart.
# The API uses SQLite (a file, self-initialized on startup) — no database server to start.
$ErrorActionPreference = 'SilentlyContinue'

$root = Split-Path $PSScriptRoot -Parent
$api  = Join-Path $root 'apps\api'
$web  = Join-Path $root 'apps\web'

Write-Host '== ApexOS: (re)starting ==' -ForegroundColor Cyan

# 1) Free the ports (so this also works as a restart)
foreach ($port in 8000, 3000) {
  Get-NetTCPConnection -LocalPort $port -State Listen -EA SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -EA SilentlyContinue }
}

# 2) API — own window, with hot reload (SQLite schema self-initializes on boot)
Start-Process powershell -ArgumentList @('-NoExit','-Command',
  "cd `"$api`"; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000")

# 3) Web — own window, dev mode (hot reload)
Start-Process powershell -ArgumentList @('-NoExit','-Command',
  "cd `"$web`"; npm run dev")

Write-Host ''
Write-Host 'ApexOS is starting up (two windows opened for API + Web).' -ForegroundColor Green
Write-Host '  App : http://localhost:3000'
Write-Host '  API : http://localhost:8000/docs'
Write-Host 'Give it ~10s on first launch, then open the App URL.'
