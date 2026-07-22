# Running ApexOS locally

## Prerequisites
- Docker (for Postgres) — or a local Postgres 16
- Python 3.11+ and Node 18+

## 1. Start the database
```bash
docker compose up -d db
```
This runs Postgres on `localhost:5432` (db `apexos`, user/pass `apex`/`apex`).

## 2. Backend (apps/api)
```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp ../../.env.example .env          # then keep the backend section
alembic upgrade head                # create the schema
python -m app.seed                  # load real Apex master data + a demo order
uvicorn app.main:app --reload       # http://localhost:8000  (docs at /docs)
```

## 3. Frontend (apps/web)
```bash
cd apps/web
npm install
cp .env.local.example .env.local
npm run dev                         # http://localhost:3000
```

## One-shot (everything in Docker)
```bash
docker compose up --build           # db + api (migrate + seed + serve)
# then run the web app locally as in step 3
```

## Smoke test
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/dashboard/summary
```
