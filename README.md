# ApexOS

The internal **operating system** of **Apex Supply Solutions Pvt. Ltd.** — a B2B procurement
company supplying recurring operational consumables (first market: HoReCa).

> Not an ERP clone. Not another inventory tool. Software built for one company, the way Apple
> builds software for Apple. Minimal, fast, keyboard-first — like Linear, Stripe, Notion, Vercel.

## Status

**Phase 0 — Architecture & Design.** Full design system-of-record lives in [`docs/`](./docs/README.md).
Start with [`docs/00-canonical-foundation.md`](./docs/00-canonical-foundation.md).

## Stack

- **App:** one FastAPI process serving server-rendered **Jinja2** HTML (no build step) + the JSON API
- **API:** Python · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · SQLite (self-initializing, no migration tool)
- **Run:** `uvicorn app.main:app` — one command · **Storage:** local disk (Cloudflare R2 optional)

## Principles

- Single-tenant, Business Unit as a first-class dimension.
- Data-drive the nouns, code the verbs — nothing hardcoded to restaurants.
- Append-only ledgers for stock & money; money as integer minor units.
- Spine-first: prove one vertical slice end-to-end before widening.
- Every screen answers: **What happened? · What needs attention? · What should I do?**
