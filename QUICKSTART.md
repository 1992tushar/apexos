# ApexOS — Quick Start

How to start and open the app locally. Everything is already installed and the database already
has demo data — you just need to start three things.

> Use a **normal (non-admin) PowerShell**. (Postgres won't run under an elevated/admin shell.)

## Start (three terminals)

**1 — Database** (port 5433):
```powershell
cd "C:\Imp Data\Personal\apexos"
.\scripts\db.ps1 start
```

**2 — API** (http://localhost:8000):
```powershell
cd "C:\Imp Data\Personal\apexos\apps\api"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

**3 — Web app** (http://localhost:3000):
```powershell
cd "C:\Imp Data\Personal\apexos\apps\web"
npm run dev
```

## Open it

- **App:** http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

## Stop

- Web / API: `Ctrl+C` in their terminals.
- Database: `.\scripts\db.ps1 stop`  (or just leave it running.)

## If something's off

- **DB won't start / "another server might be running":** check `.\scripts\db.ps1 status`.
- **API errors about the database:** make sure step 1 ran and shows `accepting connections`.
- **Reset demo data to a clean state** (from `apps/api`):
  ```powershell
  .\.venv\Scripts\python.exe -m alembic upgrade head
  .\.venv\Scripts\python.exe -m app.seed
  ```
- The database lives at `C:\ApexOS-localdb\pgdata`. Connection string is in `apps/api\.env`
  (`postgresql+psycopg://apex:apex@localhost:5433/apexos`).

See `PROGRESS.md` for full build status and history.
