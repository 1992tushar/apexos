# Running ApexOS locally

One process. The FastAPI app serves both the JSON API **and** the server-rendered
web UI (Jinja2), and it uses **SQLite** (a file, created automatically) — so there
is no database server and no separate frontend build.

## Prerequisites
- Python 3.11+

## Run (Windows, no setup)
Double-click **`start.cmd`** in the repo root. First launch creates
`apps/api/.venv`, installs dependencies, seeds the demo data and opens the app;
every later launch just restarts it (it frees port 8000 first).

For a Desktop icon, run **`Create-Desktop-Shortcut.cmd`** once. It writes an
"ApexOS" shortcut to your Desktop that points at *your* clone — which is why the
shortcut is generated rather than committed: a `.lnk` stores an absolute path.

## Run (apps/api)
```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp ../../.env.example .env          # optional; defaults work out of the box
python -m app.seed                  # optional: creates apexos.db + Apex master data + a demo order
uvicorn app.main:app --reload       # http://localhost:8000
```
- **App (UI):** http://localhost:8000/
- **API docs (Swagger):** http://localhost:8000/docs

The schema self-initializes on startup (`Base.metadata.create_all`), so `uvicorn`
works against a fresh `apexos.db` even without seeding — the seed just adds data.

## One-shot (Docker)
```bash
docker compose up --build           # seeds SQLite + serves the app on :8000
```

## Smoke test
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/dashboard/summary
```

## Reset demo data
```bash
rm apexos.db && python -m app.seed
```
