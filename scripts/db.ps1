# ApexOS local database control.
#   .\scripts\db.ps1 start   # start Postgres (port 5433)
#   .\scripts\db.ps1 stop    # stop it
#   .\scripts\db.ps1 status  # is it up?
#
# The cluster lives at C:\ApexOS-localdb\pgdata (outside the project, no spaces in path).
# Run this from a NORMAL (non-admin) PowerShell — Postgres refuses to run under an admin token.
param([ValidateSet('start','stop','status')] [string]$cmd = 'status')

$pgbin  = 'C:\Program Files\PostgreSQL\18\bin'
$pgdata = 'C:\ApexOS-localdb\pgdata'
$logf   = 'C:\ApexOS-localdb\server.log'

switch ($cmd) {
  'start'  { & "$pgbin\pg_ctl.exe" -D $pgdata -l $logf -w start }
  'stop'   { & "$pgbin\pg_ctl.exe" -D $pgdata -m fast stop }
  'status' { & "$pgbin\pg_isready.exe" -h localhost -p 5433 }
}
