# ApexOS — Coding Standards

> **Status:** Approved · **Owner:** Architecture · **Version:** 1.0 · **Date:** 2026-07-19
>
> Conforms to `00-canonical-foundation.md` (esp. §6 naming) and extends `10-folder-structure.md`
> and `11-naming-standards.md`. Where this document and the foundation disagree, the foundation
> wins. This document defines **how we write code** — the rules a reviewer enforces and CI checks.
> Every example uses real Apex constructs from the domain glossary (Foundation §4).

---

## 1. Non-Negotiables (the short list)

1. **Type safety is not optional.** TS `strict` on; Python `mypy --strict`. No `any`, no `# type: ignore`
   without a linked reason.
2. **Layering is a contract.** Routers are thin, services hold logic, repositories hold queries.
   No ORM in routers, no HTTP in services, no business rules in repositories.
3. **Money is integer minor units** (paise) + explicit `currency`. Never a float (D5).
4. **Every error is a typed exception mapped to one error envelope.** No bare `raise Exception`,
   no leaking stack traces to clients.
5. **Every request carries a correlation id**, logged structurally, returned in the response header.
6. **Every public function and every endpoint is documented.** Docstring / JSDoc, no exceptions.
7. **The spine (`sales-order`, D4) is the reference.** Copy its shape; do not invent a new one.

CI (`ci.yml`) blocks merge on: ruff, black `--check`, mypy strict, eslint, prettier `--check`,
`tsc --noEmit`, and the test suite with coverage gates (§8).

---

## 2. Type Safety

### 2.1 TypeScript

- `tsconfig` (base `@apexos/config-ts`) sets `strict: true`, `noUncheckedIndexedAccess: true`,
  `noImplicitOverride: true`, `exactOptionalPropertyTypes: true`, `verbatimModuleSyntax: true`.
- **No `any`.** Use `unknown` at boundaries and narrow. `eslint` `@typescript-eslint/no-explicit-any`
  is an error. `@ts-expect-error` (never `@ts-ignore`) must carry a trailing reason comment.
- **No hand-written response DTOs.** Import from `@apexos/types` (generated from the API's OpenAPI).
  Foundation §6 / naming §3.
- Validate every external input (network, env, `localStorage`, URL params) with Zod, then infer the
  type — never cast. `env.ts` is Zod-validated `NEXT_PUBLIC_*`.
- Prefer discriminated unions over optional-flag bags; model impossible states as unrepresentable.

### 2.2 Python

- `mypy --strict` on the whole `apps/api`. Pydantic v2 models everywhere data crosses a boundary.
- **No untyped defs, no `Any`.** Use `typing`/`collections.abc` generics; annotate every parameter and
  return. A justified `# type: ignore[code]` must name the error code and a reason.
- SQLAlchemy 2.0 typed models via `Mapped[...]` / `mapped_column(...)` — no legacy `Column` assignment.
- Money is `int` (minor units) end-to-end. `Decimal` only appears transiently inside a computation that
  immediately rounds back to `int` minor units (§7). Never `float` for money — ever.
- Enum-like domain values live in `*_type` master tables (D2), not Python `Enum`. Truly-fixed enums
  (e.g. `payment.direction`) may be a `Literal["in", "out"]` / `StrEnum`, documented.

---

## 3. Layering — Router → Service → Repository

The layering contract from `10-folder-structure.md` §4, made enforceable. Dependency direction is
**one way and never reversed**: `router → service → repository → models`.

| Layer | Owns | Must NOT |
|-------|------|----------|
| `router.py` | HTTP concerns: parse/validate via schema, resolve `Depends`, call **one** service method, map result to a `Read` schema, set status code. | Touch the ORM, write queries, make business decisions, open transactions. |
| `service.py` | Business logic, transaction boundaries, cross-repository orchestration, code/number allocation, event emission (`activity_log`). | Import `Request`/`Response`, know about HTTP status, contain raw SQL. |
| `repository.py` | SQLAlchemy queries and persistence. Returns ORM models / primitives. | Contain business rules, emit events, know about Pydantic schemas. |
| `models.py` | Database shape (ORM). | Contain API-shaping logic. |
| `schemas.py` | API shape (Pydantic `Create`/`Update`/`Read`). | Leak D6/D7 columns that shouldn't be public. |

Cross-module calls go through the other module's **service** (its public interface), never its
`repository` or `models`. Transactions are owned by the service and committed once per use-case
(unit of work); repositories `flush` but do not `commit`.

### 3.1 Worked backend endpoint — `POST /api/v1/sales-orders`

```python
# app/modules/sales_order/repository.py — queries ONLY, no business rules
class SalesOrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, order: SalesOrder) -> SalesOrder:
        """Stage a new SalesOrder for persistence (flush, no commit)."""
        self._session.add(order)
        self._session.flush()
        return order

    def next_order_no(self, business_unit_id: UUID, period: str) -> str:
        """Allocate the next per-BU monthly SO number, e.g. SO-202607-00042."""
        seq = self._session.execute(
            text("SELECT next_document_seq(:bu, 'SO', :period)"),
            {"bu": business_unit_id, "period": period},
        ).scalar_one()
        return f"SO-{period}-{seq:05d}"
```

```python
# app/modules/sales_order/service.py — business logic + transaction boundary
class SalesOrderService:
    def __init__(
        self,
        orders: SalesOrderRepository,
        customers: CustomerService,
        events: EventEmitter,
    ) -> None:
        self._orders = orders
        self._customers = customers
        self._events = events

    def create_order(self, payload: SalesOrderCreate, actor: User) -> SalesOrder:
        """Validate credit, allocate SO number, compute totals (minor units), persist, emit event.

        Raises:
            CreditHoldError: customer is on credit hold (mapped to HTTP 409).
            EntityNotFoundError: customer does not exist (HTTP 404).
        """
        self._customers.assert_can_order(payload.customer_id)  # raises typed errors
        period = utcnow().strftime("%Y%m")
        order = SalesOrder(
            id=uuid7(),
            order_no=self._orders.next_order_no(payload.business_unit_id, period),
            customer_id=payload.customer_id,
            business_unit_id=payload.business_unit_id,
            created_by=actor.id,
        )
        order.lines = [self._build_line(l) for l in payload.lines]
        order.total_minor = sum(line.line_total_minor for line in order.lines)  # int paise
        self._orders.add(order)
        self._events.emit(SALES_ORDER_CREATED, entity=order, actor=actor)
        return order
```

```python
# app/modules/sales_order/router.py — THIN: parse → call service → return Read schema
router = APIRouter(prefix="/api/v1/sales-orders", tags=["sales-orders"])

@router.post("", response_model=SalesOrderRead, status_code=201)
def create_sales_order(
    payload: SalesOrderCreate,
    service: SalesOrderService = Depends(get_sales_order_service),
    actor: User = Depends(get_current_user),
) -> SalesOrder:
    """Create a Sales Order for the current Business Unit and return the created record."""
    return service.create_order(payload, actor)
```

Note what is **absent** from the router: no query, no `session.commit()`, no `try/except` mapping —
the typed exceptions from the service are turned into the error envelope by the global handler (§4).

---

## 4. Error Handling

One typed exception hierarchy → one error envelope. No endpoint builds its own error shape.

### 4.1 Exception hierarchy (backend)

```python
# app/core/errors.py
class AppError(Exception):
    """Base for all expected, mapped application errors."""
    code: str = "app_error"          # stable machine code, snake_case
    http_status: int = 400

class EntityNotFoundError(AppError):
    code = "entity_not_found"; http_status = 404

class ValidationConflictError(AppError):
    code = "validation_conflict"; http_status = 409

class CreditHoldError(ValidationConflictError):
    code = "credit_hold"             # inherits 409
```

### 4.2 The error envelope (the ONE client-facing shape)

```jsonc
{
  "error": {
    "code": "credit_hold",                       // stable, documented, client-switchable
    "message": "Customer Blue Café is on credit hold.",
    "details": [ { "field": "customer_id", "issue": "credit_hold" } ], // optional
    "correlation_id": "01J8Z6R2K3W…"             // matches X-Correlation-Id header + logs
  }
}
```

- A single FastAPI exception handler maps `AppError` → envelope + `http_status`; Pydantic
  `RequestValidationError` → `code: "validation_error"`, 422, with per-field `details`; any
  **unhandled** exception → `code: "internal_error"`, 500, message scrubbed, full trace logged
  with the correlation id.
- Never `raise Exception("...")` or `raise HTTPException` inside a service — raise a typed `AppError`.
  Routers raise nothing; they let service errors propagate to the handler.
- **Frontend** parses this envelope in `lib/api-client.ts` and throws an `ApiError` carrying `code`,
  `message`, `correlationId`. UI switches on `code` (typed), shows `message` in a **Toast**, and logs
  `correlationId` for support. Success responses are unwrapped to data.

---

## 5. Validation

Two layers, never one. The client validates for UX; the server validates for truth. The server
**never trusts** client validation.

| Boundary | Tool | Where |
|----------|------|-------|
| Form / client input | **Zod** schema (`xxxSchema`) + RHF resolver | `features/*/schema` |
| Request body / query | **Pydantic v2** (`XxxCreate`/`Update`) | `modules/*/schemas.py` |
| Env | Zod (`env.ts`) / Pydantic `Settings` (`config.py`) | per app |
| DB invariants | constraints (`uq_*`, FK, `CHECK`), not just app code | migrations |

- The Zod schema and the Pydantic schema describe the **same contract**; keep them in sync
  (the OpenAPI-generated `@apexos/types` is the reference). Divergence is a review finding.
- Cross-entity / stateful rules (credit limit, stock availability, unique SKU) are **business
  validation** and live in the **service**, raising typed `AppError`s — not in Zod/Pydantic, which
  only cover shape and simple field rules.

---

## 6. Structured Logging & Correlation Id

- **`structlog`** (JSON in prod, pretty in dev), configured in `app/core/logging.py`. No bare
  `print`, no stdlib `logging` calls in feature code.
- Middleware reads or mints an `X-Correlation-Id` per request, binds it (plus `user_id`, `bu_id`,
  `route`) into the log context, and echoes it on the response. Every log line in that request
  carries it automatically.
- Log **events, not sentences**: `log.info("sales_order.created", order_no=…, total_minor=…)`.
  Event names mirror the domain events in `11-naming-standards.md` §5.
- **Never log secrets or PII** (tokens, full card/contact data). Money logs as `_minor` ints.
- Levels: `debug` (dev detail), `info` (business events), `warning` (recoverable/degraded),
  `error` (failed operation, with `exc_info`). 5xx paths always log at `error` with the trace.
- Frontend: a thin logger tags client errors with the last-seen `correlationId` so a UI report ties
  to the server trace.

---

## 7. Money & Decimal Rules (D5)

- **Store, transport, and compute money as `int` minor units** (paise; 1 INR = 100 paise). Column
  suffix `_minor`; pair with `currency` (`char(3)`, default `INR`).
- Rounding happens **once, explicitly**, at the smallest sensible line (GST per invoice line before
  summing — see naming §6 commit example) using banker's rounding (`ROUND_HALF_EVEN`) on `Decimal`,
  then cast straight back to `int`. Never accumulate floats.
- **Display** conversion (minor → `₹42,180.00`, `Asia/Kolkata`) lives only in `lib/format.ts` on the
  frontend. The backend never formats currency for display.
- Percentages/margins are computed from minor-unit ints and returned as integers or basis points,
  not floats, where they must round-trip.

```python
def gst_minor(taxable_minor: int, rate_bps: int) -> int:
    """GST for one line in paise. rate_bps = GST rate in basis points (1800 = 18%)."""
    cents = Decimal(taxable_minor) * Decimal(rate_bps) / Decimal(10_000)
    return int(cents.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
```

---

## 8. Testing Strategy

The spine is delivered to production quality (D4) — that means tested at every layer.

| Tier | Scope | Stack | What it proves |
|------|-------|-------|----------------|
| **Unit** | One service/function; repository mocked | pytest / Vitest | Business logic + edge cases (credit hold, rounding, sequence). |
| **Service** | Service against a **real repository + test DB** | pytest + Postgres (testcontainers) | Persistence + transaction correctness. |
| **Integration** | Router → service → DB via `TestClient` | pytest + `TestClient` | Contract: status codes, error envelope, auth. |
| **Component / hook** | UI + hooks, network mocked (MSW) | Vitest + RTL | Rendering, states (loading/empty/error), form validation. |
| **E2E** | Full stack, real browser, happy + key sad paths | Playwright (`apps/web/tests/e2e`) | The user journey works. |

- **Coverage gates (CI):** backend service + repository layers **≥ 90%**; overall backend **≥ 85%**;
  frontend features **≥ 80%**. Coverage is a floor, not a target — test behavior, not lines.
- **Factories, not fixtures-by-hand.** `polyfactory`/`factory_boy` in `apps/api/tests/factories`
  produce valid domain objects (a `SalesOrderFactory` with real-looking `AUR-TIS-001` lines). RTL
  render helpers on the frontend.
- Every bug fix ships with a **regression test** that fails before the fix. Every typed `AppError`
  path has a test asserting its `code` and status. Tests are deterministic — no real network, no
  `sleep`, seeded clocks/ids.
- Test names state behavior: `test_create_order_rejects_customer_on_credit_hold`.

---

## 9. Documentation Rules

- **Every function documented.** Python: a docstring (summary line; `Args`/`Returns`/`Raises` when
  non-obvious — always list the typed errors a service method raises). TS: a JSDoc block on every
  exported function, hook, and component describing purpose and non-obvious params.
- **Every endpoint documented.** FastAPI: `summary`/`description`, `response_model`, documented
  status codes and error `code`s. The OpenAPI doc is the API's public contract and generates
  `@apexos/types` — keep it accurate.
- **Comment the *why*, not the *what*.** The code says what; comments explain intent, trade-offs, and
  links to the ADR (`20-decisions-log.md`) or the founder sheet a rule comes from.
- Each feature module carries a short `README`/module docstring: what it owns, its events, its public
  service methods. Architectural changes update the relevant `docs/*` and log an ADR.

---

## 10. Lint & Format

| Concern | Backend (`apps/api`) | Frontend (`apps/web`) |
|---------|----------------------|-----------------------|
| Format | **black** (line length 100) | **prettier** |
| Lint | **ruff** (pyflakes, isort, pyupgrade, bugbear, simplify) | **eslint** (`@apexos/config-eslint`) |
| Types | **mypy --strict** | **tsc --noEmit** (`strict`) |
| Config | `pyproject.toml` | root prettier + `.eslintrc.cjs`, `tsconfig.json` |

- Formatting is not a review topic — the formatter decides. CI runs `--check`; a formatting diff
  fails the build. Pre-commit hooks run ruff + black + eslint + prettier on staged files.
- No disabling a lint rule inline without a trailing reason comment. Repo-wide rule changes go
  through review, not a local `// eslint-disable`.
- Imports ordered by the tool (ruff isort / eslint import-order); no unused imports or vars.

---

## 11. Worked Frontend Feature Call — schema → hook → component

Mirrors the backend endpoint above. Direction: `component → hook → api → schema/types`
(`10-folder-structure.md` §5.2).

```ts
// features/sales-order/schema/sales-order-schema.ts — Zod, mirrors the Pydantic contract
export const salesOrderCreateSchema = z.object({
  customerId: z.string().uuid(),
  businessUnitId: z.string().uuid(),
  lines: z.array(
    z.object({
      productId: z.string().uuid(),
      qty: z.number().int().positive(),
      unitPriceMinor: z.number().int().nonnegative(), // paise, never a float
    }),
  ).min(1, "Add at least one line"),
});
export type SalesOrderCreateInput = z.infer<typeof salesOrderCreateSchema>;
```

```ts
// features/sales-order/api/sales-order-api.ts — the ONLY place this feature calls the backend
import { apiClient } from "@/lib/api-client";
import type { SalesOrderReadDTO } from "@apexos/types"; // generated, never hand-written

/** Create a Sales Order. Throws ApiError (with .code) on the error envelope. */
export function createSalesOrder(input: SalesOrderCreateInput): Promise<SalesOrderReadDTO> {
  return apiClient.post<SalesOrderReadDTO>("/api/v1/sales-orders", input);
}
```

```ts
// features/sales-order/hooks/use-sales-orders.ts — TanStack Query mutation hook
/** Mutation to create a Sales Order; invalidates the list and surfaces a toast on error. */
export function useCreateSalesOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createSalesOrder,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sales-orders"] }),
    onError: (e: ApiError) => toast.error(e.message), // e.code drives typed handling
  });
}
```

```tsx
// features/sales-order/components/SalesOrderForm.tsx — RHF + Zod resolver, thin UI
/** Sales Order create form. Validates with Zod, submits via useCreateSalesOrder. */
export function SalesOrderForm() {
  const form = useForm<SalesOrderCreateInput>({ resolver: zodResolver(salesOrderCreateSchema) });
  const { mutate, isPending } = useCreateSalesOrder();
  const onSubmit = form.handleSubmit((values) => mutate(values));
  return (
    <form onSubmit={onSubmit} className="space-y-6">
      {/* fields via shadcn/ui + FormField; see 17-design-system.md §form spec */}
      <Button type="submit" disabled={isPending}>Create order</Button>
    </form>
  );
}
```

---

## 12. PR Review Checklist

A PR is not approvable until every box is true. Reviewers reject on any unchecked item.

**Correctness & scope**
- [ ] Single, coherent concern; commit(s) follow Conventional Commits (naming §6).
- [ ] Conforms to the foundation and naming standards; no hardcoded market/restaurant assumptions (D1/D2).
- [ ] Money is integer `_minor` + `currency`; no floats; rounding is explicit and once (§7).

**Layering & types**
- [ ] Router thin; logic in service; queries in repository; no ORM in router; no HTTP in service (§3).
- [ ] No `any` / untyped defs; DTOs imported from `@apexos/types`; `mypy`/`tsc` clean (§2).
- [ ] Cross-module access via the other module's service only.

**Safety**
- [ ] Errors are typed `AppError`s → error envelope; no leaked traces; correct status codes (§4).
- [ ] Validated at both boundaries (Zod + Pydantic) and business rules in the service (§5).
- [ ] Structured logs with correlation id; no secrets/PII logged (§6).

**Quality**
- [ ] Tests at the right tiers; coverage gates met; a regression test for any bug fix (§8).
- [ ] Every new function/endpoint documented; ADR/`docs` updated if architecture changed (§9).
- [ ] ruff/black/eslint/prettier clean; no un-reasoned lint disables (§10).
- [ ] Loading / empty / error states handled in the UI (see `17-design-system.md`).
- [ ] Migration reviewed (indexes, FKs, audit + `business_unit_id` columns), reversible.
```
