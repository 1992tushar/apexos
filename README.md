# ApexOS

The internal **operating system** of **Apex Supply Solutions Pvt. Ltd.** — a B2B procurement
company supplying recurring operational consumables (first market: HoReCa).

> Not an ERP clone. Not another inventory tool. Software built for one company, the way Apple
> builds software for Apple. Minimal, fast, keyboard-first — like Linear, Stripe, Notion, Vercel.

## Status

**Phase 0 — Architecture & Design.** Full design system-of-record lives in [`docs/`](./docs/README.md).
Start with [`docs/00-canonical-foundation.md`](./docs/00-canonical-foundation.md).

## Stack

- **Web:** Next.js (App Router) · React · TypeScript · Tailwind · shadcn/ui · TanStack Table · Recharts
- **API:** Python · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · SQLite (self-initializing, no migration tool)
- **Auth:** Clerk · **Storage:** Cloudflare R2 · **Deploy:** Docker → Railway/Render → K8s

## Principles

- Single-tenant, Business Unit as a first-class dimension.
- Data-drive the nouns, code the verbs — nothing hardcoded to restaurants.
- Append-only ledgers for stock & money; money as integer minor units.
- Spine-first: prove one vertical slice end-to-end before widening.
- Every screen answers: **What happened? · What needs attention? · What should I do?**
