# Creates an "ApexOS" shortcut on the current user's Desktop that launches this clone.
#
# Why this exists instead of a committed .lnk: a Windows shortcut stores an ABSOLUTE
# target path, so a checked-in .lnk would point at whoever created it. This generates
# one against the folder you actually cloned into.
$ErrorActionPreference = 'Stop'

$root    = Split-Path $PSScriptRoot -Parent
$target  = Join-Path $root 'start.cmd'
# GetFolderPath handles OneDrive-redirected Desktops correctly.
$desktop = [Environment]::GetFolderPath('Desktop')
$link    = Join-Path $desktop 'ApexOS.lnk'

if (-not (Test-Path $target)) { throw "start.cmd not found at $target" }

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($link)
$sc.TargetPath       = $target
$sc.WorkingDirectory = $root
$sc.Description      = 'Start ApexOS (UI + API on http://localhost:8000)'
$sc.WindowStyle      = 1
$icon = Join-Path $root 'docs\apexos.ico'
if (Test-Path $icon) { $sc.IconLocation = "$icon,0" }
$sc.Save()

Write-Host "Created shortcut: $link" -ForegroundColor Green
Write-Host "  -> launches: $target"
Write-Host 'Double-click "ApexOS" on your Desktop to start the app.'
