# ApexOS — Backup & Recovery Strategy

> **Status:** Approved · **Owner:** DevOps + Finance · **Version:** 1.0 · **Date:** 2026-07-19
>
> Conforms to `00-canonical-foundation.md`. Where this document and the foundation disagree,
> **the foundation wins**. This document defines how ApexOS's data survives failure, corruption,
> and disaster: Postgres backups, R2 durability, the restore runbook, testing cadence, and
> business-continuity notes. Security of backups (encryption, access) is specified in
> `13-security-design.md`.

---

## 0. What we're protecting & why it's non-negotiable

ApexOS holds Apex's **operational and financial system of record** — append-only ledgers (D3) for
stock, invoices, bills, and payments; pricing/margin; customer credit; GST data. Under D3, **balances
are derived from movements**, so the ledger *is* the truth — losing it is unrecoverable by any other
means. Indian **GST/company-law retention** obligations make multi-year durability a legal requirement,
not just an ops nicety.

**Two data stores to protect:**

| Store | Contents | Backup mechanism |
|---|---|---|
| **PostgreSQL** | All relational data — every entity in foundation §5 | PITR/WAL + daily logical + snapshots |
| **Cloudflare R2** | `document` files (foundation §5) | Bucket versioning + lifecycle + cross-location durability |

**Backups are secondary state.** The primary system stays authoritative; backups exist only to restore
it. Every backup is **encrypted at rest** and access-controlled (`13-security-design.md` §3–§4).

---

## 1. PostgreSQL backup

Three complementary layers — you need all three, because each covers a different failure mode.

### 1.1 Continuous — PITR via WAL archiving (corruption / "oops" recovery)

- **Write-Ahead Log (WAL) shipped continuously** to object storage (R2/S3-compatible), giving
  **Point-in-Time Recovery** to any moment within the retention window.
- Covers the worst case for an append-only financial system: a bad migration or erroneous bulk
  operation at 14:07 → restore to **14:06:59**, losing seconds, not a day.
- **RPO from WAL: ≤ 5 minutes** (WAL segment/timeout flush). This is the tightest recovery granularity.

### 1.2 Daily — logical + physical snapshots (routine restore)

- **Nightly `pg_dump`** (logical, compressed, custom format) — portable, restores selectively (single
  table/schema), survives major-version moves. Run during the low-traffic window (IST night).
- **Managed platform snapshot** (Railway/Render managed Postgres, later a K8s volume snapshot) — fast
  full-cluster physical restore.
- Each dump is **checksummed** on creation; the checksum is verified on restore-test (§4).

### 1.3 Retention tiers (grandfather-father-son)

| Tier | Type | Retention | Purpose |
|---|---|---|---|
| **WAL / PITR** | Continuous | **7–14 days** | Fine-grained recovery from recent corruption |
| **Daily** | `pg_dump` + snapshot | **30 days** | Routine restore, recent history |
| **Weekly** | `pg_dump` | **12 weeks** | Medium-term rollback |
| **Monthly** | `pg_dump` | **12 months** | Year-over-year, audit |
| **Yearly** | `pg_dump` (immutable, WORM) | **7+ years** | **GST/statutory retention** (India) |

- Older tiers are **cold storage** (cheaper R2 class), **immutable/WORM** for the yearly statutory tier
  so they can't be altered or ransomware-encrypted.
- All tiers **encrypted** (`13-security-design.md` §4.1); keys in the secret store, separate from the
  data.
- **3-2-1 principle:** ≥3 copies, ≥2 media/locations, ≥1 off-platform (a second cloud region/provider
  for the encrypted dumps) so a full platform-account compromise doesn't take the backups with it.

---

## 2. Cloudflare R2 durability & versioning

R2 stores `document` files (foundation §5). R2 provides high built-in redundancy; we add:

- **Object versioning enabled** on document buckets — an overwrite or delete keeps prior versions, so a
  bad overwrite or accidental delete is recoverable.
- **Lifecycle rules:** noncurrent versions retained **90 days**, then expired; incomplete multipart
  uploads aborted after 7 days.
- **Delete protection:** the API never issues hard deletes on `document` objects — `document.delete`
  (RBAC §4) is a **soft delete** (D7) that unlinks in Postgres; the object + its versions persist under
  lifecycle policy.
- **Secondary copy:** critical documents (invoices, GST records, signed contracts) are additionally
  synced to an **off-platform encrypted bucket** on the same cadence as the yearly Postgres tier — same
  3-2-1 discipline.
- **Consistency with Postgres:** because file bytes live in R2 and metadata in Postgres, a full DR
  restore restores **both** to a consistent point (§3); orphan/dangling references are reconciled by a
  post-restore integrity job.

---

## 3. Restore runbook (RTO / RPO)

### 3.1 Objectives

| Metric | Target | Meaning |
|---|---|---|
| **RPO** (max data loss) | **≤ 5 min** (PITR) · ≤ 24 h (daily-only fallback) | We can recover to within 5 minutes via WAL |
| **RTO** (max downtime) | **≤ 2 h** (routine) · ≤ 4 h (full DR) | Time to a working, verified system |

RTO/RPO are tightest for **prod**; lower environments are best-effort.

### 3.2 Scenarios & procedures

**Scenario A — Logical corruption / bad data (most common).** Restore to a point in time.

1. **Declare & freeze:** put the API into maintenance/read-only, announce, open an incident record.
2. **Identify T** — the last-good timestamp (from `activity_log`, D10, which pinpoints the offending
   event).
3. **Provision** a fresh Postgres target (do **not** overwrite the live cluster yet).
4. **Restore** base snapshot + **replay WAL to just before T** (PITR).
5. **Verify** (§3.3) on the restored target.
6. **Cut over:** repoint the API DSN to the restored cluster; lift maintenance.

**Scenario B — Full loss of the Postgres instance/region.**

1. Provision new managed Postgres (or K8s Postgres) in a healthy region.
2. Restore the **latest daily** physical/logical backup, then **replay available WAL** to minimize loss.
3. Restore R2 (already region-redundant; promote secondary if primary region is down).
4. Reconcile Postgres↔R2 (integrity job), verify (§3.3), cut over DNS/DSN.

**Scenario C — Accidental document delete/overwrite (R2).**

1. Restore the prior **object version** (§2) for the affected key(s).
2. Re-link in Postgres if the metadata was also soft-deleted.

**Scenario D — Ransomware / platform-account compromise.**

1. Rotate all credentials (`13-security-design.md` §3, §12).
2. Rebuild infrastructure clean; restore from the **immutable/off-platform** encrypted tier (§1.3, §2).
3. Full verify before exposing to users.

### 3.3 Post-restore verification (gate before cut-over)

- Row counts + checksums match the backup manifest.
- **Ledger integrity (D3):** `stock_balance` reconciles from `stock_movement`; `receivable`/`payable`
  reconcile from invoices/bills minus payment allocations. **This is the definitive correctness check**
  for a financial restore.
- Latest `activity_log` entries are consistent and continuous up to T.
- Alembic **migration head matches the application version** (`15-deployment-strategy.md`) — no
  schema drift.
- Smoke test the spine (D4): open a customer → product → sales order → invoice → dashboard tile.
- App connects to R2; a sample `document` presigned-GET succeeds.

---

## 4. Backup testing cadence

**An untested backup is a hope, not a backup.**

| Test | Cadence | What it proves |
|---|---|---|
| Automated restore-to-scratch + row/checksum verify | **Weekly** | Backups are readable and complete |
| Ledger-integrity reconciliation on the restored copy | **Weekly** | D3 truth survives the round-trip |
| Full DR game-day (Scenario B, timed against RTO/RPO) | **Quarterly** | We can actually recover in time |
| R2 version-restore drill (Scenario C) | **Quarterly** | Document recovery works |
| Immutable/off-platform tier restore (Scenario D) | **Semi-annually** | Ransomware/DR path works |
| Retention/expiry audit (tiers age correctly, yearly WORM intact) | **Monthly** | Statutory retention is real |

- Restore tests target an **isolated scratch environment** (never prod), with **anonymized** data if
  surfaced to anyone (`13-security-design.md` §10).
- Each test's result (pass/fail, measured RTO/RPO) is logged; a failure opens a priority incident.
- Alerting: **a missed or failed nightly backup pages DevOps** — silent backup failure is treated as a
  Sev-2.

---

## 5. Business-continuity notes

- **Blast-radius by design:** append-only ledgers (D3) + full audit (D7/D10) mean most incidents are
  **recoverable by replay/PITR without data loss**, not just by full restore. The architecture is the
  first line of BC.
- **Single-tenant simplicity:** one company's data ⇒ one restore scope; no tenant-by-tenant recovery
  complexity (D1). Restores are all-or-nothing to a point in time, which keeps the runbook simple.
- **Degraded-mode operation:** if the API is down but backups are safe, the business can operate on the
  documented SOPs (`sop` index, foundation §5) short-term; ApexOS reconciles on recovery because entry
  is event-based.
- **Prod→lower-env refresh:** restoring prod data into staging/dev for testing is done **anonymized**
  (mask PII contacts, GSTIN; scramble names) — prod data never flows downhill unmasked
  (`13-security-design.md` §10).
- **Ownership & escalation:** DevOps owns backup operations; **Finance signs off** on retention meeting
  GST/statutory needs (they own the compliance requirement). RTO/RPO targets and any DR game-day result
  are reviewed with the Founder/Admin.
- **Dependencies documented:** recovery depends on Clerk (auth), Cloudflare (edge/R2), and the DB
  platform being reachable; the runbook lists the alternate region/provider for each so recovery isn't
  blocked on a single vendor.
- **Roadmap tie-in:** Redis (foundation §3, `16-future-roadmap.md`) is a **cache**, treated as
  **ephemeral** — it is intentionally *not* backed up; it rebuilds from Postgres on restart. Keeping
  cache disposable is a deliberate BC simplification.
