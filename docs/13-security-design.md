# ApexOS — Security Design

> **Status:** Approved · **Owner:** Security + DevOps · **Version:** 1.0 · **Date:** 2026-07-19
>
> Conforms to `00-canonical-foundation.md`. Where this document and the foundation disagree,
> **the foundation wins**. This document defines how ApexOS authenticates, authorizes, protects
> data, and defends itself. The RBAC model itself is defined in `03-user-roles-and-permissions.md`
> — this document **references** it and never redefines roles, permissions, or the matrix.

---

## 0. Threat context & posture

ApexOS is a **single-tenant** (D1) internal OS for one company's known, small team. That shrinks
the attack surface (no anonymous signups, no tenant-isolation bugs) but raises the stakes: it holds
Apex's **pricing, margins, supplier terms, customer credit, and GST/financial records** — the crown
jewels of a B2B procurement business. Our posture:

- **Assume-breach for authorization.** Every state-changing call is re-checked server-side (§2); the
  UI is never trusted.
- **Deny by default** (RBAC §1): no `user_role` ⇒ zero access.
- **Append-only truth** (D3) + **full audit** (D7, D10): even a compromised insider leaves a trail.
- **Least privilege** everywhere — roles, secrets, network, R2 tokens, CI.
- **Defense in depth:** edge (Clerk/Cloudflare) → app (RBAC + validation) → data (encryption, RLS-style
  BU scoping) → audit (activity_log).

---

## 1. Authentication flow (Clerk → server verification → our RBAC)

Auth is **Clerk** (D8) for the internal team, wrapped behind our own `user`/`role`/`permission`
tables so **we own authorization** (RBAC §1). Clerk answers *"who are you?"*; ApexOS answers
*"what may you do?"*.

```
Browser (Next.js)                 FastAPI (api)                     Postgres
──────────────────                ─────────────                     ────────
1. Clerk sign-in (hosted UI,
   MFA, session cookie/JWT)
        │
2. Short-lived Clerk session JWT ──▶ 3. verify JWT signature (Clerk JWKS,
   attached to every /api call         cached), check exp/iss/aud
                                        │
                                     4. clerk_user_id ──▶ SELECT user WHERE clerk_user_id
                                        │                 (must exist & is_active) ───────▶ user row
                                     5. load effective permissions
                                        (union of active user_role→role→
                                        role_permission), cached per-request ─────────────▶ perms + bu_scope
                                        │
                                     6. build AuthContext{user, perms, bu_scope}
                                        │
                                     7. require(...) dependency gates the route (RBAC §7)
```

**Steps in words:**

1. The user signs in through Clerk's hosted flow (email + password / SSO), **MFA enforced** for all
   accounts, **required** for `founder_admin` and `finance_accounts`.
2. Clerk issues a **short-lived session JWT** (default 60s templated token, refreshed by Clerk SDK).
   Next.js attaches it as a Bearer token on every call to the API.
3. The API verifies the JWT **signature** against Clerk's JWKS (fetched once, cached with rotation),
   and validates `exp`, `iss` (our Clerk instance), and `aud`. Invalid ⇒ `401`. **We never trust a
   decoded-but-unverified token.**
4. `clerk_user_id` (the JWT `sub`) maps to exactly one `user` row (unique per RBAC table spec). No row,
   or `is_active = false` ⇒ `403` (deactivated/offboarded users, RBAC §8).
5. Effective permissions = union of all permissions across the user's active `user_role` rows, plus
   the **BU scope** (set of `business_unit_id`; a `NULL` row ⇒ all BUs). Computed once and cached
   **per request only** — no long-lived permission cache, so a role change takes effect on the next
   request (RBAC §8).
6. An `AuthContext{user, perms, bu_scope}` is built and injected into the route.
7. The `require(*codes)` dependency enforces the permission check (RBAC §7).

**Onboarding/offboarding** is driven by **Clerk webhooks** (RBAC §8): `user.created` →
create inactive `user` row; `user.deleted`/`session.revoked` → set `is_active = false`. Webhooks are
**signature-verified** (Svix signing secret) — an unsigned or stale webhook is rejected.

**Service-to-service / no-user contexts** (CI migrations, scheduled jobs, QBO sync worker) use a
distinct **service principal** — a dedicated `user` row flagged `is_service`, granted only the exact
permissions it needs, and authenticated by a separate machine credential (not a Clerk session).

---

## 2. Authorization enforcement points

RBAC §7 is authoritative. The enforcement **choke points**, in order of the request lifecycle:

| # | Layer | Enforces | Mechanism | On failure |
|---|-------|----------|-----------|-----------|
| 1 | Edge / Next.js middleware | Authenticated session exists | Clerk middleware; unauthenticated → redirect to sign-in | Redirect (UI) |
| 2 | API route dependency | Permission code present | `require("sales_order.create")` (RBAC §7) | `403` + audit |
| 3 | Service layer | Approval **thresholds** (RBAC §5) | value vs. BU `setting` → self-approve or `pending_approval` | `pending_approval` + task |
| 4 | Repository layer | **BU scope** (RBAC §6) | `WHERE business_unit_id = ANY(:bu_scope)` injected once | Rows filtered out |
| 5 | Database | Ownership/write-authority, constraints | FK + CHECK constraints; append-only ledgers (D3) | Constraint error |
| 6 | UI (`can()` / `<Can>`) | **Cosmetic** hide/disable only | `/api/v1/me` permission set | Button hidden (non-authoritative) |

**Key rules (from RBAC §6–§7):**

- The **authoritative** check is always server-side. UI gating is convenience only — a hidden button
  called directly still returns `403`.
- BU scope is enforced in the **repository layer** (single choke point) so it can never be forgotten
  per-endpoint.
- Thresholds live in the **service layer**, never in the route.
- An **unknown permission code referenced in code is a deploy-blocking CI error** — every code must
  exist in the seed migration (RBAC §4, §7). CI diff-checks the matrix against `seed_roles_permissions.py`.
- Every allow/deny on a **state-changing** route writes an `activity_log` row (D10) in the same
  transaction as the change.

---

## 3. Secrets management

**Principle: no secret in source, ever.** `.env.example` documents every variable with **no values**
(see `10-folder-structure.md`).

| Secret class | Examples | Where it lives | Rotation |
|---|---|---|---|
| Auth | Clerk secret key, JWKS, webhook signing secret | Platform secret store (Railway/Render env → K8s Secrets/External Secrets later) | On suspected exposure; Clerk keys per Clerk policy |
| Database | Postgres DSN, per-env credentials | Platform secret store; injected at runtime | Quarterly + on offboarding of anyone with prod access |
| Storage | R2 access key / secret, bucket scoping | Platform secret store; **scoped tokens** per bucket (§7) | Quarterly |
| External | QuickBooks OAuth client id/secret + refresh tokens | Secret store; refresh tokens encrypted at rest (§4) | Per QBO policy; refresh-token rotation on use |
| Signing | JWT verification keys (Clerk-managed), webhook secrets | Clerk / secret store | Provider-managed |
| CI | GitHub Actions deploy tokens, registry creds | **GitHub Actions encrypted secrets**, environment-scoped | Quarterly; least-privilege deploy tokens |

**Controls:**

- Secrets are **injected as environment variables at runtime**, never baked into Docker images
  (`15-deployment-strategy.md` §config). Images are built once, promoted across envs; **only config
  differs per env**.
- **Per-environment isolation** (§10): dev/staging/prod each have distinct secrets. A leaked dev key
  cannot touch prod.
- **Secret scanning** in CI (gitleaks/GitHub secret scanning) blocks commits/PRs that introduce a
  credential.
- **No secret is logged.** Structured logging (foundation §3) redacts known secret keys and PII (§4).
- **Least-privilege access:** only Founder/Admin and the DevOps principal can read prod secrets; access
  is itself auditable at the platform layer.

---

## 4. Data protection

### 4.1 Encryption

- **In transit:** TLS 1.2+ everywhere — browser↔edge (Cloudflare), edge↔api, api↔Postgres (`sslmode=require`),
  api↔R2 (HTTPS), api↔Clerk/QBO. **No plaintext** hops. HSTS at the edge.
- **At rest:** Postgres volume encryption (platform-managed, AES-256) + R2 server-side encryption
  (S3-compatible SSE). **Backups are encrypted** (`14-backup-strategy.md`).
- **Application-level encryption** for the most sensitive fields at rest beyond disk encryption: QBO
  **refresh tokens** and any stored external credentials are encrypted with an app key (envelope
  encryption; key in the secret store).

### 4.2 PII & financial/GST data

ApexOS holds limited PII (customer/supplier **contacts**: names, emails, phones, addresses; internal
**users**) and heavy **financial data** (pricing, margins, invoices, bills, payments, credit, **GSTIN**).

- **Data classification:** `Public` · `Internal` · `Confidential` (pricing, margin, credit) ·
  `Restricted` (financial ledgers, GSTIN, credentials). Restricted/Confidential get the tightest RBAC
  grants (see the margin/pricing/finance rows in RBAC §4 — most roles get **view-only or nothing**).
- **Least-exposure by RBAC:** margin, buy prices, and finance ledgers are visible only to the roles the
  matrix grants (RBAC §4). BU scoping (RBAC §6) further narrows every list.
- **GST/financial integrity:** money is **integer minor units** (D5) — no float drift; financial records
  are **append-only ledgers** (D3) — invoices/bills/payments are never mutated, only superseded/voided
  with an audit trail. This is both a correctness and an anti-tamper control.
- **Log redaction:** PII and financial identifiers (GSTIN, full contact details, tokens) are redacted
  from application logs; only IDs are logged.
- **Data minimization & retention:** we store only what the business needs. Financial records are
  retained per Indian statutory requirements (GST/company law — multi-year); soft-deleted (D7) rather
  than hard-deleted so nothing auditable is lost. Retention/erasure of PII contacts on request is
  handled by anonymization, preserving ledger integrity.
- **Right to correct/erase:** because contacts are separate from ledgers, a contact can be anonymized
  without breaking historical invoices (which reference immutable snapshots).

---

## 5. Audit logging (`activity_log`, D10)

Every domain event is recorded in `activity_log` (D10, foundation §5) — **actor, verb, entity,
before/after** — inside the **same transaction** as the state change (module breakdown rule). This
powers both the Dashboard "What happened?" feed and the security audit trail.

- **Coverage:** every state-changing service verb writes exactly one row. Authorization **denials** on
  state-changing routes are also recorded (RBAC §7 failure semantics).
- **Immutability:** `activity_log` is **append-only** — no update/delete path exists in code; it carries
  D7 audit columns but is never soft-deleted.
- **Sensitive events flagged:** role grants (esp. `founder_admin` — break-glass, RBAC §8), threshold
  self-approvals/escalations (RBAC §5), stock adjustments (`stock_movement.adjust`), voids
  (invoice/bill/PO/SO), and secret/config changes raise higher-visibility entries + notifications.
- **Who can read it:** `activity_log.view` is granted only to Founder/Admin, Ops Manager, Finance, and
  Auditor (RBAC §4). The Auditor role is **read-everything, change-nothing** — the compliance lens.
- **Tamper evidence:** because ledgers are append-only and the log is append-only, a malicious edit
  leaves a derivable inconsistency (balances derived from movements won't reconcile).

---

## 6. Input validation

Validation is layered and **fails closed**:

- **Frontend:** React Hook Form + **Zod** schemas (foundation §3) — UX-level, not trusted.
- **API boundary:** **Pydantic v2** schemas (`Create`/`Update`/`Read`, naming standards) validate and
  coerce every request body, query, and path param. Unknown fields rejected; types strict.
- **Business rules:** the **service layer** enforces invariants (e.g. money is minor-unit integer D5,
  discount within threshold RBAC §5, BU scope RBAC §6).
- **Persistence:** SQLAlchemy 2.0 **parameterized queries** everywhere — **no string-built SQL** ⇒
  SQL-injection closed by construction. DB-level CHECK/FK/UNIQUE constraints are the last line.
- **Output encoding:** React escapes by default (XSS mitigated); we never `dangerouslySetInnerHTML`
  untrusted content. API returns JSON only.
- **File inputs:** validated separately (§8).

---

## 7. Rate limiting & abuse controls

- **Edge:** Cloudflare rate limiting + WAF in front of `web` and `api` (bot/DDoS mitigation, IP
  reputation). This is the first tier and covers volumetric abuse.
- **Auth:** Clerk enforces its own login rate limiting / lockout / bot protection on the sign-in flow.
- **API:** per-principal rate limits at the FastAPI layer (token-bucket, keyed by `user.id`), stricter
  on expensive/sensitive endpoints (exports, reports, `finance.export`, `report.export`, QBO sync).
  **Redis-backed** once Redis lands (foundation §3 "Redis later"); in-process/DB-backed limiter until
  then.
- **Write throttling:** state-changing endpoints get tighter budgets than reads; repeated `403`s from a
  principal raise a security notification.
- **Idempotency:** create endpoints for financial/stock actions accept an idempotency key to prevent
  duplicate ledger rows on retries.

---

## 8. File-upload security (Cloudflare R2)

`document` entities are files in R2 (foundation §4/§5), linked to any entity. Upload path:

1. **Authorize:** `document.upload` permission required (RBAC §4); BU scope applies to the linked entity.
2. **Presigned, direct-to-R2 upload:** the API issues a **short-lived presigned PUT** scoped to a single
   object key; the browser uploads straight to R2 (the API never proxies file bytes). Keys are
   **UUID-v7-namespaced** (`bu/<bu_id>/<entity>/<uuid7>`), never user-supplied filenames.
3. **Validate:** enforce **max size**, an **allowlist of content types** (PDF/image/office docs — the
   real document types), and verify the actual magic bytes match the declared type server-side on
   finalize. Reject mismatches.
4. **Sanitize:** original filename stored as metadata only (display), never used as the storage key or
   in a shell/path context. Strip/normalize on display.
5. **Serve private:** the R2 bucket is **private** (no public read). Downloads go through **short-lived
   presigned GET** URLs minted only after a `document.view` check. No object is ever world-readable.
6. **Scoped tokens:** the API's R2 credentials are **bucket-scoped, least-privilege** (separate tokens
   per env, §3/§10). No account-wide keys.
7. **Malware posture:** treat all uploads as untrusted; content-type allowlist + size caps + no
   server-side execution of uploaded content. AV scanning (e.g. an async scan-on-upload worker) is a
   Phase-2 hardening item.
8. **Versioning/durability** for uploaded documents is covered in `14-backup-strategy.md` (R2 versioning).

---

## 9. Dependency & supply-chain hygiene

- **Lockfiles committed** — `pnpm-lock.yaml` (web) and a pinned Python lock (uv/poetry) for api —
  reproducible builds; no floating versions.
- **Automated updates:** Dependabot/Renovate PRs for both ecosystems; security patches expedited.
- **Vulnerability scanning in CI** (`15-deployment-strategy.md`): `pnpm audit` / `pip-audit`, plus
  **container image scanning** (Trivy) on built images before deploy. High/critical blocks the pipeline.
- **SAST + secret scanning** (CodeQL, gitleaks) on every PR.
- **Provenance:** images built only by CI from a tagged commit; **no local pushes to registries**. Pin
  base images by digest; minimal base images (slim/distroless where possible) to shrink surface.
- **SBOM** generated per image build for auditability.
- **Third-party surface:** Clerk (auth), Cloudflare (edge + R2), QuickBooks (finance bridge) — each is a
  trust boundary reviewed and least-privilege-scoped; QBO is a **candidate system-of-record bridge**
  (foundation §3), accessed with rotating OAuth refresh tokens (§3/§4).

---

## 10. Environment isolation (dev / staging / prod)

Three fully isolated environments (detailed in `15-deployment-strategy.md`):

| Aspect | dev | staging | prod |
|---|---|---|---|
| Data | synthetic/seed only | **anonymized** copy or synthetic | real business data |
| Secrets | dev-only keys | staging-only keys | prod-only keys (tightest access) |
| Clerk instance | dev instance | staging instance | production instance |
| R2 buckets | dev buckets/tokens | staging buckets/tokens | prod buckets/tokens |
| Access | whole team | DevOps + QA | **Founder/Admin + DevOps only** |
| Deploy trigger | on PR/branch | on merge to main | on tagged release + approval gate |

- **No cross-environment credential reuse.** Each env's secrets are independent (§3).
- **Prod data never flows downhill unmasked.** Restores into lower envs are anonymized
  (`14-backup-strategy.md` business-continuity notes).
- **Least prod access:** only Founder/Admin and DevOps reach prod secrets/DB; all such access is audited
  at the platform layer.

---

## 11. STRIDE-lite threat model

Scoped to ApexOS's real assets: **auth, RBAC, pricing/margin, financial/GST ledgers, R2 documents,
supply chain**. Each threat maps to the mitigation already specified above (or in referenced docs).

| STRIDE | Threat (ApexOS-specific) | Primary mitigation | Ref |
|---|---|---|---|
| **S**poofing | Forged/replayed session; impersonating a user or the webhook sender | Clerk JWT signature + `exp`/`iss`/`aud` verification; short-lived tokens; Svix-signed webhooks; MFA (Founder/Finance mandatory) | §1 |
| **S**poofing | Stolen service credential acts as the app | Distinct least-privilege service principals; scoped machine creds; per-env secrets | §1, §3, §10 |
| **T**ampering | Editing an invoice/payment/stock balance to hide fraud | Append-only ledgers (D3); balances **derived** not stored; DB constraints; `activity_log` before/after | §5, D3 |
| **T**ampering | SQL injection / request tampering | Pydantic validation; parameterized SQLAlchemy; DB constraints | §6 |
| **T**ampering | Malicious/oversized/mis-typed file upload | Content-type allowlist + magic-byte check + size cap; server-generated keys; private bucket | §8 |
| **R**epudiation | Insider denies making a change | `activity_log` (actor+verb+before/after) in-transaction (D10); append-only; Auditor role | §5 |
| **I**nfo disclosure | Leaking pricing/margin/credit/GST to a role that shouldn't see it | RBAC matrix (view-only/none for sensitive rows); BU scoping; data classification | §2, §4, RBAC §4/§6 |
| **I**nfo disclosure | Secret in source, logs, or image | Secret store + `.env.example` only; secret scanning; log redaction; secrets not baked into images | §3, §4 |
| **I**nfo disclosure | Public R2 object / guessable URL | Private bucket; short-lived presigned GET after `document.view`; UUID-v7 keys | §8 |
| **I**nfo disclosure | Data-in-transit interception | TLS 1.2+ end to end; HSTS | §4.1 |
| **D**enial of service | Volumetric flood / expensive-endpoint abuse | Cloudflare WAF + edge rate limit; per-principal API limits; export/report throttles; idempotency | §7 |
| **E**levation of privilege | Missing server-side check; relying on hidden UI | Server-side `require()` on every route; UI purely cosmetic; unknown code = deploy-blocking CI error | §2, RBAC §7 |
| **E**levation of privilege | Bypassing approval thresholds | Thresholds in service layer, data-driven `setting`, self-approve vs. escalate logged | §2, RBAC §5 |
| **E**levation of privilege | Unauthorized `founder_admin` grant (break-glass) | Only Founder/Admin can grant; high-priority notification to all admins; audited | §5, RBAC §8 |
| **E**levation of privilege | Cross-BU data access | Repository-layer BU scope (single choke point) | §2, RBAC §6 |
| **S**upply chain | Compromised dependency or base image | Pinned lockfiles; Dependabot/Renovate; `pip-audit`/`pnpm audit`; Trivy image scan; CI-only builds; SBOM | §9 |

---

## 12. Incident response (brief)

- **Detect:** error tracking + structured logs + `activity_log` anomalies + repeated-`403`/rate-limit
  alerts (`15-deployment-strategy.md` observability).
- **Contain:** deactivate the affected Clerk user (webhook → `is_active=false`), rotate the implicated
  secret (§3), revoke R2/QBO tokens.
- **Eradicate/recover:** deploy the fix forward (forward-only migrations, `15`); restore from encrypted
  backups if data integrity is in question (`14-backup-strategy.md` restore runbook).
- **Review:** post-incident ADR logged in `20-decisions-log.md`; audit trail from `activity_log`
  reconstructs the timeline.

---

## 13. Security checklist (per feature, enforced in review)

- [ ] Every new route declares `require(<permission_code>)` and the code exists in the seed (RBAC §4).
- [ ] Repository methods take and apply `bu_scope` (RBAC §6).
- [ ] Thresholded actions compute tier in the service layer (RBAC §5).
- [ ] Request bodies/params have Pydantic schemas; no raw SQL.
- [ ] State-changing verbs write one `activity_log` row in-transaction (D10).
- [ ] No secret, PII, or GSTIN in logs or source.
- [ ] File uploads go through presigned + validated path (§8).
- [ ] New dependency passes audit + scan; lockfile updated (§9).
