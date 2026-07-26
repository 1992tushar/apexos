# ApexOS — start / restart the app in one go.
# The single FastAPI process serves BOTH the web UI (Jinja) and the JSON API,
# backed by a SQLite file (self-initialized on startup) — no DB server, no web build.
#
# Safe to run on a fresh clone: it creates the virtualenv, installs deps and seeds
# the demo data on first launch, then just starts the app on every launch after.
# Frees port 8000 first, so this doubles as a restart.
$ErrorActionPreference = 'Stop'

$root = Split-Path $PSScriptRoot -Parent
$api  = Join-Path $root 'apps\api'
$venv = Join-Path $api '.venv'
$py   = Join-Path $venv 'Scripts\python.exe'
$db   = Join-Path $api 'apexos.db'

Write-Host '== ApexOS: (re)starting ==' -ForegroundColor Cyan

# --- First-run bootstrap ------------------------------------------------------
if (-not (Test-Path $py)) {
  $host_py = (Get-Command py -EA SilentlyContinue), (Get-Command python -EA SilentlyContinue) |
             Where-Object { $_ } | Select-Object -First 1
  if (-not $host_py) {
    Write-Host 'Python 3.11+ was not found on PATH. Install it from https://python.org and re-run.' -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
  }
  Write-Host "First run: creating virtualenv in apps\api\.venv ..." -ForegroundColor Yellow
  & $host_py.Source -m venv $venv
}

# Install (or repair) dependencies only when the package isn't importable yet.
# EAP is relaxed around the probe: a failed import is expected on a fresh venv.
$ErrorActionPreference = 'Continue'
& $py -c 'import app.main' *> $null
$installed = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = 'Stop'
if (-not $installed) {
  Write-Host 'Installing dependencies (one-time, ~1 min) ...' -ForegroundColor Yellow
  & $py -m pip install --upgrade pip --quiet
  Push-Location $api
  try { & $py -m pip install -e '.[dev]' } finally { Pop-Location }
}

# Seed demo data once, so the first page load isn't empty.
if (-not (Test-Path $db)) {
  Write-Host 'Seeding demo data (Apex master data + a demo order) ...' -ForegroundColor Yellow
  Push-Location $api
  try { & $py -m app.seed } catch { Write-Host "Seed skipped: $_" -ForegroundColor DarkYellow } finally { Pop-Location }
}

# --- Free port 8000 (so this also works as a restart) -------------------------
Get-NetTCPConnection -LocalPort 8000 -State Listen -EA SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force -EA SilentlyContinue }

# --- API + UI — own window, with hot reload ----------------------------------
# Single-quote the inner path: PowerShell wraps a spacey -ArgumentList element in
# double quotes, so embedded double quotes would mangle the child's command line.
$cmd = "Set-Location '$api'; & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --port 8000"
Start-Process powershell -WorkingDirectory $api -ArgumentList @('-NoExit','-NoProfile','-Command', $cmd)

Write-Host ''
Write-Host 'ApexOS is starting up.' -ForegroundColor Green
Write-Host '  App : http://localhost:8000/'
Write-Host '  API : http://localhost:8000/docs'
Write-Host 'Give it ~5s on first launch, then open the App URL.'
