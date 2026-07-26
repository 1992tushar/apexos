# ApexOS — Quick Start

One command. The API and the web UI are the same process now (Jinja server-rendered
pages), backed by a SQLite file — no database server, no separate frontend.

## Start (double-click)
Double-click **`start.cmd`** in the repo root. On a fresh clone it creates the
virtualenv, installs dependencies and seeds demo data before booting; after that
it just starts (and restarts) the app.

Want a Desktop icon? Run **`Create-Desktop-Shortcut.cmd`** once — it drops an
"ApexOS" shortcut on your Desktop pointing at your own clone.

## Start (one terminal)
```powershell
cd apps\api
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

## Open it
- **App:** http://localhost:8000/
- **API docs (Swagger):** http://localhost:8000/docs

## Stop
- `Ctrl+C` in the terminal.

## If something's off
- The SQLite file `apps/api/apexos.db` self-initializes on startup; if it looks
  corrupt, delete it and re-seed.
- **Reset demo data** (from `apps/api`):
  ```powershell
  Remove-Item apexos.db -ErrorAction SilentlyContinue
  .\.venv\Scripts\python.exe -m app.seed
  ```
- Connection string lives in `apps/api\.env` (`sqlite:///./apexos.db`).

See `PROGRESS.md` for full build status and history.
