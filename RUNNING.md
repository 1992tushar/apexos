# Running ApexOS locally

## Prerequisites
- Python 3.11+ and Node 18+
- No database server needed — the API uses **SQLite** (a file, created automatically).

## 1. Backend (apps/api)
```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp ../../.env.example .env          # then keep the backend section
python -m app.seed                  # creates apexos.db + loads Apex master data + a demo order
uvicorn app.main:app --reload       # http://localhost:8000  (docs at /docs)
```
The schema self-initializes on startup (`Base.metadata.create_all`), so `uvicorn`
works against a fresh `apexos.db` even without seeding — the seed just adds data.

## 2. Frontend (apps/web)
```bash
cd apps/web
npm install
cp .env.local.example .env.local
npm run dev                         # http://localhost:3000
```

## One-shot (API in Docker)
```bash
docker compose up --build           # seeds SQLite + serves the API on :8000
# then run the web app locally as in step 2
```

## Smoke test
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/dashboard/summary
```

## Reset demo data
Delete the SQLite file and re-seed (from `apps/api`):
```bash
rm apexos.db && python -m app.seed
```
