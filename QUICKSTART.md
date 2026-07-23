# ApexOS — Quick Start

How to start and open the app locally. Everything is already installed and the database file
already has demo data — you just need to start two things. The API uses **SQLite** (a file), so
there's no database server to start.

## Start (two terminals)

**1 — API** (http://localhost:8000):
```powershell
cd "C:\Imp Data\Personal\apexos\apps\api"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

**2 — Web app** (http://localhost:3000):
```powershell
cd "C:\Imp Data\Personal\apexos\apps\web"
npm run dev
```

## Open it

- **App:** http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

## Stop

- Web / API: `Ctrl+C` in their terminals.

## If something's off

- **API errors about the database:** the SQLite file `apps/api/apexos.db` self-initializes on
  startup; if it looks corrupt, delete it and re-seed.
- **Reset demo data to a clean state** (from `apps/api`):
  ```powershell
  Remove-Item apexos.db -ErrorAction SilentlyContinue
  .\.venv\Scripts\python.exe -m app.seed
  ```
- The connection string lives in `apps/api\.env` (`sqlite:///./apexos.db`).

See `PROGRESS.md` for full build status and history.
