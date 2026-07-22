# ApexOS — start / restart the whole stack (Database + API + Web) in one go.
# Run from a NORMAL (non-admin) PowerShell. Kills any running instances first, so it's also a restart.
$ErrorActionPreference = 'SilentlyContinue'

$root   = Split-Path $PSScriptRoot -Parent
$pgbin  = 'C:\Program Files\PostgreSQL\18\bin'
$pgdata = 'C:\ApexOS-localdb\pgdata'
$api    = Join-Path $root 'apps\api'
$web    = Join-Path $root 'apps\web'

Write-Host '== ApexOS: (re)starting ==' -ForegroundColor Cyan

# 1) Free the ports (so this also works as a restart)
foreach ($port in 8000, 3000) {
  Get-NetTCPConnection -LocalPort $port -State Listen -EA SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -EA SilentlyContinue }
}

# 2) Database (start only if not already up)
& "$pgbin\pg_isready.exe" -h localhost -p 5433 *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host 'Starting database (port 5433)...'
  & "$pgbin\pg_ctl.exe" -D $pgdata -l 'C:\ApexOS-localdb\server.log' -w start | Out-Null
} else {
  Write-Host 'Database already running (port 5433).'
}

# 3) API — own window, with hot reload
Start-Process powershell -ArgumentList @('-NoExit','-Command',
  "cd `"$api`"; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000")

# 4) Web — own window, dev mode (hot reload)
Start-Process powershell -ArgumentList @('-NoExit','-Command',
  "cd `"$web`"; npm run dev")

Write-Host ''
Write-Host 'ApexOS is starting up (two windows opened for API + Web).' -ForegroundColor Green
Write-Host '  App : http://localhost:3000'
Write-Host '  API : http://localhost:8000/docs'
Write-Host 'Give it ~10s on first launch, then open the App URL.'
