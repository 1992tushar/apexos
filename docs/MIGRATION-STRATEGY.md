# ApexOS — Schema Migration Strategy

> How the database schema changes, in dev and in production. Satisfies **R1.8**
> (WS5). This supersedes the Alembic sections of `07-database-er-diagram.md` and
> `15-deployment-strategy.md`, which describe the retired Postgres-only stack.
>
> **Version:** 1.0 · **Date:** 2026-07-28 · Part 1, checkpoint C3

---

## The decision

**Two modes, selected by `DATABASE_URL`.**

| | Dev / demo (today) | Production (when it exists) |
|---|---|---|
| Engine | SQLite file — `sqlite:///./apexos.db` | PostgreSQL via `DATABASE_URL` |
| Schema creation | `Base.metadata.create_all` in the `app.main` lifespan | Alembic, reintroduced |
| Schema evolution | `_ensure_new_columns` — additive `ALTER`s | Alembic revisions |
| Authority | The models are the schema | The migration chain is the schema |

The stack-lightening commit removed Alembic entirely (2026-07-23) because a
single-file SQLite database that any machine can recreate from `app/seed/` in
one second does not benefit from a migration chain — it benefits from *not having
one*. That trade is correct for dev and wrong for prod, so the two are decided
separately rather than forcing one tool to serve both.

---

## Dev: `create_all` plus an additive shim

`app.main.lifespan` imports every model so `Base.metadata` is complete, then calls
`create_all`, then `_ensure_new_columns`. All three are idempotent, so they run on
every boot.

`create_all` has one blind spot that matters: **it creates whole missing tables
and never `ALTER`s an existing one.** Add a column to a model that already has a
table and `create_all` silently does nothing — the app then fails at query time
against a database that looks fine. `_ensure_new_columns` closes exactly that gap
and nothing more:

```python
_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "document": {"category": "VARCHAR(32) NOT NULL DEFAULT 'other'"},
}
```

Each entry is checked against the live column list before the `ALTER`, so it is a
no-op once applied.

### Rules for using the shim

1. **Additive only.** New columns must be nullable or carry a `DEFAULT`. The shim
   cannot rename, retype, drop, or backfill — SQLite barely can either.
2. **Add the column to the model *and* the shim.** The model is what `create_all`
   uses for a fresh database; the shim is what patches an existing one. Both, or
   the two paths disagree.
3. **Anything else, recreate the file.** Renames, type changes, drops, data
   backfills: delete `apexos.db` and re-run `python -m app.seed`. There is no
   production data to lose (D-C — starting fresh, no migration), which is
   precisely what makes this cheap.
4. **Extend the seed** so new columns and new screens have demo data (G14) — a new `app/seed/<domain>.py` section plus one call in `run()`, never appended to `run()`.

### Why not keep Alembic for dev too

A migration chain for a database you throw away is pure ceremony: every schema
change costs a revision file, and the failure mode — a chain that diverges from
the models — is *worse* than the one it prevents, because `create_all` at least
cannot lie about a table's existence. The shim is ~10 lines and its scope is
visible in one screen.

---

## Production: Alembic behind `DATABASE_URL`

**Trigger:** the first deployment with data worth keeping.

Production reverses the trade. The database holds data nobody can recreate,
migrations must be reviewable before they run, and they must be reversible. That
is Alembic's job, and nothing about the current code blocks reintroducing it —
`DATABASE_URL` already swaps the engine, and the models were made dialect-agnostic
during stack-lightening (`Uuid()` not `PGUUID`, `JSON` not `JSONB`, `JSON` not
`ARRAY(String)`), so they describe a Postgres schema as accurately as a SQLite one.

Reintroduction steps, in order:

1. `pip install alembic`; `alembic init alembic`; point `env.py` at
   `app.db.metadata.Base.metadata` and `settings.database_url`.
2. `alembic revision --autogenerate -m "baseline"` against an empty Postgres
   database. Review it — autogenerate is a first draft, not an answer.
3. `alembic stamp head` on any database created by `create_all`, so the existing
   schema is adopted rather than re-created.
4. **Make `create_all` and the shim dev-only:** gate them on the URL being SQLite,
   so a Postgres deployment can only ever be migrated by Alembic. Two tools
   writing the same production schema is the failure this ordering prevents.
5. Fold every `_ADDITIVE_COLUMNS` entry into the baseline revision and empty the
   dict.
6. Run migrations as an explicit deploy step, never from the app's lifespan — an
   app that migrates on boot cannot be scaled to two instances safely.

Until step 1, `_ADDITIVE_COLUMNS` is the migration history, and this document is
where that is written down.

---

## Where the code is

| Concern | Location |
|---|---|
| Model imports + `create_all` | `apps/api/app/main.py` — `lifespan` |
| Additive column shim | `apps/api/app/main.py` — `_ADDITIVE_COLUMNS`, `_ensure_new_columns` |
| Declarative base, mixins | `apps/api/app/db/base.py` |
| Metadata / model registry | `apps/api/app/db/metadata.py` |
| Engine + `DATABASE_URL` | `apps/api/app/core/database.py`, `app/core/config.py` |
| Demo data | `apps/api/app/seed/` (one module per section) |
