"""Credit policy: versioning the terms, and enforcing the limit (R8.3, R8.6–R8.9).

Two jobs that belong together because they read the same row:

* **`set_policy`** appends a new version and closes the previous one. A policy is never
  edited in place — that would destroy the answer to "what limit were they on when we
  approved that order?", which is the only reason to keep history.
* **`check`** decides whether an order may be confirmed, and **says why in numbers**. R8.7
  makes that acceptance, not politeness: "credit limit exceeded" tells the founder nothing
  they can act on, while "limit 50,000, outstanding 47,500, this order 4,000, short by
  1,500" tells them exactly how much to collect or how far to override.

**The boundary is exact and it is integer arithmetic** (R8.9/G1). Money is integer minor
units end to end, so "at the limit" is `<=` on two ints — no float is involved anywhere,
and one minor unit over is genuinely blocked rather than lost to rounding.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.money import minor_to_text
from app.db.explain import Explained, Input, SourceRecord
from app.modules.activity.history import CHANGES_KEY, field_changes
from app.modules.activity.service import ActivityService
from app.modules.customers.models import Customer, CustomerCreditPolicy
from app.modules.customers.repository import CustomerRepository
from app.modules.customers.schemas import CreditDecision, CreditPolicyRead


class CreditPolicyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CustomerRepository(db)
        self.activity = ActivityService(db)

    def _require_customer(self, customer_id: uuid.UUID) -> Customer:
        customer = self.repo.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found")
        return customer

    # --- R8.3: versioned terms -------------------------------------------

    def current(self, customer_id: uuid.UUID) -> CustomerCreditPolicy | None:
        return self.repo.current_credit_policy(customer_id)

    def history(self, customer_id: uuid.UUID) -> list[CreditPolicyRead]:
        """Every version, newest first. The current one is `valid_to IS NULL`.

        Ordered by `id` as well as `valid_from` because `valid_from` defaults to
        `func.now()` and ties for rows written in one transaction — the trap Part 5 hit.
        Keys are UUID v7 and time-ordered, so `id` breaks it by real write order.
        """
        rows = self.db.scalars(
            select(CustomerCreditPolicy)
            .where(
                CustomerCreditPolicy.customer_id == customer_id,
                CustomerCreditPolicy.deleted_at.is_(None),
            )
            .order_by(
                CustomerCreditPolicy.valid_from.desc(), CustomerCreditPolicy.id.desc()
            )
        )
        return [
            CreditPolicyRead(
                id=row.id,
                credit_limit_minor=row.credit_limit_minor,
                payment_terms_days=row.payment_terms_days,
                delivery_preference=row.delivery_preference,
                reason=row.reason,
                valid_from=row.valid_from,
                valid_to=row.valid_to,
                is_current=row.valid_to is None,
            )
            for row in rows
        ]

    def set_policy(
        self, customer_id: uuid.UUID, payload, *, actor_id: uuid.UUID | None
    ) -> CreditPolicyRead:
        """Append a new version of the terms and close the previous one (R8.3).

        A reason is required: terms change because something was negotiated, and a version
        nobody can explain later is as useless as no history at all. Whitespace is refused
        as well as empty, for the reason R7.4 gave — `"   "` passes a length check and tells
        a later reader nothing.
        """
        customer = self._require_customer(customer_id)
        reason = (payload.reason or "").strip()
        if not reason:
            raise ValidationError(
                "Changing credit terms needs a reason — a version nobody can explain "
                "later is as good as no history"
            )

        now = datetime.now(UTC)
        previous = self.current(customer.id)
        if previous is not None:
            # Carry forward anything the caller did not name, so setting a limit does not
            # silently reset the payment terms to zero.
            limit = (
                payload.credit_limit_minor
                if payload.credit_limit_minor is not None
                else previous.credit_limit_minor
            )
            terms = (
                payload.payment_terms_days
                if payload.payment_terms_days is not None
                else previous.payment_terms_days
            )
            delivery = (
                payload.delivery_preference
                if payload.delivery_preference is not None
                else previous.delivery_preference
            )
            previous.valid_to = now
            previous.updated_by = actor_id
        else:
            limit = payload.credit_limit_minor or 0
            terms = payload.payment_terms_days or 0
            delivery = payload.delivery_preference

        version = CustomerCreditPolicy(
            customer_id=customer.id,
            credit_limit_minor=limit,
            payment_terms_days=terms,
            delivery_preference=delivery,
            reason=reason,
            status="active",
            valid_from=now,
            created_by=actor_id,
        )
        self.db.add(version)
        self.db.flush()

        # R2.10 still applies: the change-history panel must show the field-level
        # before/after. Versioning moved WHERE that diff lives — onto this row, which also
        # carries the reason — but it must not make it disappear. `field_changes` renders a
        # `*_minor` field as rupees without touching a float (G1).
        baseline = previous or CustomerCreditPolicy(
            customer_id=customer.id, credit_limit_minor=0, payment_terms_days=0
        )
        changes = field_changes(
            baseline,
            {"credit_limit_minor": limit, "payment_terms_days": terms},
        )

        self.activity.log(
            actor_id=actor_id,
            verb="updated",
            entity_type="customer",
            entity_id=customer.id,
            summary=(
                f"Credit terms for {customer.name}: limit {minor_to_text(limit)}, "
                f"{terms} days — {reason}"
            ),
            data={CHANGES_KEY: changes, "reason": reason} if changes else {"reason": reason},
        )
        return self.history(customer.id)[0]

    # --- R8.6–R8.9: the check --------------------------------------------

    def check(self, customer_id: uuid.UUID, order_total_minor: int) -> CreditDecision:
        """Would this order breach the customer's credit limit? (R8.6)

        **A limit of zero means no limit**, not "refuse everything": a customer with no
        terms recorded is on cash-and-carry as far as this build is concerned, and blocking
        every order for them would be a worse failure than allowing it.

        The comparison is `outstanding + order <= limit`, all integers (R8.9/G1). At the
        limit is allowed; one minor unit over is not.
        """
        customer = self._require_customer(customer_id)
        policy = self.current(customer.id)
        limit = policy.credit_limit_minor if policy else 0
        outstanding = self.repo.outstanding_minor(customer.id)
        exposure = outstanding + int(order_total_minor)

        if limit <= 0:
            return CreditDecision(
                customer_id=customer.id,
                customer_name=customer.name,
                allowed=True,
                limit_minor=limit,
                outstanding_minor=outstanding,
                order_total_minor=int(order_total_minor),
                unlimited=True,
            )

        return CreditDecision(
            customer_id=customer.id,
            customer_name=customer.name,
            allowed=exposure <= limit,
            limit_minor=limit,
            outstanding_minor=outstanding,
            order_total_minor=int(order_total_minor),
            unlimited=False,
        )

    def explain(self, decision: CreditDecision) -> Explained:
        """The decision through the one explanation shape (G11), so a credit block reads
        the same way as every other derived number in the product."""
        return Explained(
            what=f"Credit check — {decision.customer_name}",
            value=("within limit" if decision.allowed else "over limit"),
            formula=(
                f"outstanding {minor_to_text(decision.outstanding_minor)} + this order "
                f"{minor_to_text(decision.order_total_minor)} = "
                f"{minor_to_text(decision.exposure_minor)} against a limit of "
                f"{minor_to_text(decision.limit_minor)}"
                if not decision.unlimited
                else "no credit limit is set for this customer"
            ),
            window="current receivables",
            inputs=(
                Input(label="Credit limit", value=minor_to_text(decision.limit_minor)),
                Input(
                    label="Currently outstanding",
                    value=minor_to_text(decision.outstanding_minor),
                ),
                Input(label="This order", value=minor_to_text(decision.order_total_minor)),
                Input(
                    label="Short by",
                    value=minor_to_text(decision.shortfall_minor),
                    missing_reason=None if decision.shortfall_minor else "nothing short",
                ),
            ),
            records=(
                SourceRecord(
                    label=decision.customer_name,
                    href=f"/customers/{decision.customer_id}",
                ),
            ),
            caveat=(
                "A limit of zero means no limit is recorded, not that nothing may be sold."
                if decision.unlimited
                else None
            ),
        )

    def refusal_message(self, decision: CreditDecision) -> str:
        """R8.7 — the numbers, in one sentence the founder can act on."""
        return (
            f"{decision.customer_name} is over their credit limit: limit "
            f"{minor_to_text(decision.limit_minor)}, currently outstanding "
            f"{minor_to_text(decision.outstanding_minor)}, this order "
            f"{minor_to_text(decision.order_total_minor)} — short by "
            f"{minor_to_text(decision.shortfall_minor)}. Collect payment or override "
            f"with a reason."
        )

    def enforce(
        self,
        customer_id: uuid.UUID,
        order_total_minor: int,
        *,
        override_reason: str | None = None,
        actor_id: uuid.UUID | None = None,
        ref_label: str = "",
    ) -> CreditDecision:
        """Check, and either pass, refuse with the numbers, or record an override (R8.8).

        The override writes **exactly one** `activity_log` row (G5) naming who, when, by how
        much, and why. It is logged against the CUSTOMER, because "we went over their limit"
        is a fact about the relationship, not only about one order.
        """
        decision = self.check(customer_id, order_total_minor)
        if decision.allowed:
            return decision

        reason = (override_reason or "").strip()
        if not reason:
            raise ConflictError(self.refusal_message(decision))

        self.activity.log(
            actor_id=actor_id,
            verb="overrode",
            entity_type="customer",
            entity_id=decision.customer_id,
            summary=(
                f"Credit limit overridden for {decision.customer_name} by "
                f"{minor_to_text(decision.shortfall_minor)}"
                + (f" on {ref_label}" if ref_label else "")
                + f" — {reason}"
            ),
            data={
                "limit_minor": decision.limit_minor,
                "outstanding_minor": decision.outstanding_minor,
                "order_total_minor": decision.order_total_minor,
                "over_by_minor": decision.shortfall_minor,
                "reason": reason,
            },
        )
        return decision.model_copy(update={"overridden": True, "override_reason": reason})
