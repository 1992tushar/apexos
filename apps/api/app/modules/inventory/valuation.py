"""Part 5 C2 — what stock is worth (R6.16) and how old it is (R6.10).

**Reads only, writes nothing** (G15), and stores nothing: cost, value and age are all
derived per read from the movement ledger (G7). Kept out of `service.py` for the same
reason `suppliers/vendor.py` sits beside `suppliers/service.py` — that module is the write
half (movements, reservations, locations) and this one is pure derivation, so a checkpoint
working on one need not read the other.

**Decision D-A shapes both halves of this module.** There are NO FIFO layers and no lot
tracking, so:

* **Valuation is a simple weighted average** over acquisitions — R6.16, which replaced the
  struck R6.9. It exists ONLY to produce an on-hand *value* figure. **Margin does not read
  it** (R11.6): `MarginService.gp` is selling minus the purchase price snapshotted onto the
  line, and routing margin through a valuation layer would be the drift D-A forbids.
* **Only a PURCHASE establishes a cost basis.** Transfers move the same units between
  warehouses and both halves carry a cost hint, so counting them weights one purchase
  twice; putaway is net-zero re-addressing; an adjustment or count corrects a quantity
  rather than buying at a price. See `InventoryRepository.ACQUISITION_REASONS` — the list
  is there, next to the query, rather than being a rule buried here.
* **Ageing is an attribution, and it is approximate.** Without lots the balance on hand
  cannot be tied to particular receipts, so it is attributed to the most recent arrivals
  first — the assumption that older stock leaves first. That assumption is stated on
  screen (R6.10 requires it) and carried in the `Explained.caveat`, not left implicit.
  **This is not a FIFO layer:** nothing is stored, nothing is consumed from a layer, and
  valuation does not read it. It is one stated assumption used to bucket ages, which is
  the only way R7.8's dead-stock radar can have an input at all.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.money import minor_to_text, qty_text, round_minor
from app.db.explain import Explained, Input, SourceRecord
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    AGE_BUCKETS,
    AgeBucketRow,
    AgeingRow,
    StockValueRow,
)
from app.modules.inventory.service import InventoryService

# Spelled out once so the screen, the explanation and the test cannot disagree.
_APPROXIMATION = (
    "Approximate: without lot tracking the balance on hand cannot be tied to particular "
    "receipts, so it is attributed to the most recent arrivals first."
)


def _age_days(occurred_at: datetime, *, as_of: datetime) -> int:
    """Whole days between an arrival and now, never negative.

    SQLite hands back a naive datetime even for `DateTime(timezone=True)`, so a naive
    value is read as UTC rather than being compared against an aware one — that
    comparison raises `TypeError`, and only on SQLite, which is the worst kind of bug to
    find in production.
    """
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    return max((as_of - occurred_at).days, 0)


def bucket_for(days: int) -> tuple[str, str]:
    """Which age bucket a given age falls in. **Upper bounds are inclusive** (R6.10)."""
    for key, label, upper in AGE_BUCKETS:
        if upper is None or days <= upper:
            return key, label
    raise AssertionError("AGE_BUCKETS must end with an open-ended bucket")


class ValuationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = InventoryRepository(db)
        self.inventory = InventoryService(db)

    # --- R6.16: weighted-average cost -----------------------------------

    def cost_basis(self, product_id: uuid.UUID) -> Explained:
        """The weighted-average acquisition cost, as an `Explained` (G11).

        `SUM(qty * unit_cost) / SUM(qty)` over purchases that recorded a cost. Where no
        such purchase exists the answer is **unknown**, not zero — a zero cost basis
        would value real stock at nothing and read as a fact rather than a gap (R5.11's
        rule, applied here).
        """
        rows = self.repo.acquisition_totals(product_id)
        if not rows:
            return Explained.unknown(
                what="Weighted-average cost",
                formula="total purchase cost ÷ total quantity purchased",
                reason="no purchase with a recorded unit cost",
                window="the whole movement ledger",
            )

        _pid, qty, cost_total, purchases, first_at, last_at = rows[0]
        qty = Decimal(qty or 0)
        cost_total = Decimal(cost_total or 0)
        if qty <= 0:
            return Explained.unknown(
                what="Weighted-average cost",
                formula="total purchase cost ÷ total quantity purchased",
                reason="purchased quantity is zero",
                window="the whole movement ledger",
            )

        basis = round_minor(cost_total / qty)
        uncosted = self.repo.acquisitions_without_cost(product_id)
        inputs = [
            Input(label="Quantity purchased", value=qty_text(qty)),
            Input(label="Total purchase cost", value=minor_to_text(int(cost_total))),
            Input(label="Purchases counted", value=str(purchases)),
        ]
        if uncosted:
            inputs.append(
                Input(
                    label="Purchased without a recorded cost",
                    value=qty_text(uncosted),
                    missing_reason="excluded from the average — no unit cost on the movement",
                )
            )
        window = "the whole movement ledger"
        if first_at is not None and last_at is not None:
            window = f"{first_at:%d %b %Y} to {last_at:%d %b %Y} ({purchases} purchases)"

        return Explained(
            what="Weighted-average cost",
            value=minor_to_text(basis),
            formula=(
                f"{minor_to_text(int(cost_total))} total purchase cost ÷ "
                f"{qty_text(qty)} purchased = {minor_to_text(basis)} per unit"
            ),
            window=window,
            inputs=tuple(inputs),
            records=(SourceRecord(label=f"{purchases} purchase movements"),),
            caveat=(
                "Only purchases set the cost basis. Transfers, putaway, adjustments and "
                "counts move or correct quantity without buying at a price."
            ),
        )

    def cost_basis_minor(self, product_id: uuid.UUID) -> int | None:
        """The bare figure, for callers that do not render an explanation."""
        rows = self.repo.acquisition_totals(product_id)
        if not rows:
            return None
        _pid, qty, cost_total, *_rest = rows[0]
        qty = Decimal(qty or 0)
        if qty <= 0:
            return None
        return round_minor(Decimal(cost_total or 0) / qty)

    def stock_value(self) -> list[StockValueRow]:
        """Every product's on-hand quantity and what it is worth (R6.16).

        Two queries for the whole page — acquisition totals grouped by product, and the
        balance rows — then arithmetic. Value counts ALL on-hand stock including transit
        and quarantine: the business owns it, even where it cannot be sold today.
        """
        basis_by_product: dict[uuid.UUID, int | None] = {}
        for pid, qty, cost_total, *_rest in self.repo.acquisition_totals():
            qty = Decimal(qty or 0)
            basis_by_product[pid] = (
                round_minor(Decimal(cost_total or 0) / qty) if qty > 0 else None
            )

        on_hand: dict[uuid.UUID, tuple[str, str, Decimal]] = {}
        for pid, sku, name, _wid, _wname, qty, _reorder in self.repo.stock_rows():
            sku_code, product_name, running = on_hand.get(pid, (sku, name, Decimal(0)))
            on_hand[pid] = (sku_code, product_name, running + Decimal(qty or 0))

        rows: list[StockValueRow] = []
        for pid, (sku, name, qty) in on_hand.items():
            basis = basis_by_product.get(pid)
            rows.append(
                StockValueRow(
                    product_id=pid,
                    sku_code=sku,
                    product_name=name,
                    qty_on_hand=qty,
                    cost_basis_minor=basis,
                    value_minor=(
                        round_minor(qty * Decimal(basis)) if basis is not None else None
                    ),
                )
            )
        rows.sort(key=lambda r: -(r.value_minor or 0))
        return rows

    def total_value_minor(self, rows: list[StockValueRow] | None = None) -> int:
        """Total on-hand value. Products with an unknown cost basis contribute nothing
        and are counted separately by `unknown_basis_count` — they are not treated as
        zero-cost stock, which would understate the total silently.

        Pass `rows` when you already have them; otherwise this re-runs `stock_value`, and
        a page that calls all three helpers blind would do the work three times.
        """
        rows = self.stock_value() if rows is None else rows
        return sum(r.value_minor or 0 for r in rows)

    def unknown_basis_count(self, rows: list[StockValueRow] | None = None) -> int:
        rows = self.stock_value() if rows is None else rows
        return sum(1 for r in rows if not r.is_known and r.qty_on_hand > 0)

    # --- R6.10: stock ageing --------------------------------------------

    def ageing(
        self, warehouse_id: uuid.UUID | None = None, *, as_of: datetime | None = None
    ) -> list[AgeingRow]:
        """Split every product's balance across the age buckets.

        `as_of` is injectable so a boundary test can sit exactly on a bucket edge instead
        of depending on when the suite happens to run.
        """
        as_of = as_of or datetime.now(UTC)
        rows: list[AgeingRow] = []
        for pid, sku, name, qty in self._balances(warehouse_id):
            if qty <= 0:
                continue
            rows.append(
                self._age_one(
                    pid, sku, name, qty, warehouse_id=warehouse_id, as_of=as_of
                )
            )
        rows.sort(key=lambda r: (-r.stale_qty, r.sku_code))
        return rows

    def _balances(self, warehouse_id: uuid.UUID | None):
        seen: dict[uuid.UUID, tuple[str, str, Decimal]] = {}
        for pid, sku, name, wid, _wname, qty, _reorder in self.repo.stock_rows():
            if warehouse_id is not None and wid != warehouse_id:
                continue
            sku_code, product_name, running = seen.get(pid, (sku, name, Decimal(0)))
            seen[pid] = (sku_code, product_name, running + Decimal(qty or 0))
        return [(pid, v[0], v[1], v[2]) for pid, v in seen.items()]

    def _age_one(
        self,
        product_id: uuid.UUID,
        sku: str,
        name: str,
        qty_on_hand: Decimal,
        *,
        warehouse_id: uuid.UUID | None,
        as_of: datetime,
    ) -> AgeingRow:
        """Attribute a balance to arrivals, newest first. See the module docstring for
        why newest-first and why this is not a FIFO layer."""
        totals: dict[str, Decimal] = {key: Decimal(0) for key, _l, _u in AGE_BUCKETS}
        remaining = qty_on_hand
        oldest_days: int | None = None

        for movement in self.repo.arrivals(product_id, warehouse_id):
            if remaining <= 0:
                break
            take = min(remaining, Decimal(movement.qty_delta))
            days = _age_days(movement.occurred_at, as_of=as_of)
            key, _label = bucket_for(days)
            totals[key] += take
            remaining -= take
            oldest_days = days  # arrivals are newest-first, so the last taken is oldest

        return AgeingRow(
            product_id=product_id,
            sku_code=sku,
            product_name=name,
            qty_on_hand=qty_on_hand,
            buckets=[
                AgeBucketRow(key=key, label=label, qty=totals[key])
                for key, label, _upper in AGE_BUCKETS
            ],
            oldest_days=oldest_days,
            # Balance no arrival accounts for. Reported rather than folded into the
            # oldest bucket, which would invent an age for it.
            unattributed=remaining,
        )

    def ageing_note(self) -> str:
        """The sentence R6.10 requires on screen. One source, so the screen and the
        explanation cannot drift apart."""
        return _APPROXIMATION

    def ageing_explained(self, row: AgeingRow) -> Explained:
        """One product's ageing as an `Explained`, so it renders through the same panel
        as every other derived number (G11) rather than growing its own markup."""
        inputs = [
            Input(label=b.label, value=qty_text(b.qty)) for b in row.buckets if b.qty
        ]
        if row.unattributed:
            inputs.append(
                Input(
                    label="Not attributed to an arrival",
                    value=qty_text(row.unattributed),
                    missing_reason="no inbound movement covers this balance",
                )
            )
        return Explained(
            what=f"Age of stock on hand — {row.sku_code}",
            value=f"{row.oldest_days} days" if row.oldest_days is not None else None,
            formula=(
                "on-hand balance attributed to inbound movements, newest first; "
                "each bucket's upper bound is inclusive"
            ),
            window="every inbound movement, until the balance is accounted for",
            inputs=tuple(inputs),
            records=(SourceRecord(label=f"{qty_text(row.qty_on_hand)} on hand"),),
            unknown_reason=(
                None if row.oldest_days is not None else "no inbound movement on record"
            ),
            caveat=_APPROXIMATION,
        )
