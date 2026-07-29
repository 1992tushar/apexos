"""AR/AP ageing, the collections list and payments due (R10.5–R10.8, R10.10–R10.12).

The question this module answers is R10.7's: *who do I chase today, and why*. Everything
here is a read-only projection over the append-only ledgers — no new entity, no stored
bucket, nothing written (R10.10, G7, G15).

**One receivable, one payable.** Each party's total comes from
`CustomerRepository.outstanding_by_customer()` / `SupplierRepository.outstanding_by_supplier()`,
the bulk siblings of the two `outstanding_minor` methods, and the buckets are that same
total split by the age of the party's open documents. Where the split cannot account for
the whole total — a credit note larger than the invoice it credits, a payment against a
since-cancelled invoice — the remainder is reported as `unaged_minor` rather than folded
into a bucket, so `Σ buckets + unaged == the one receivable` holds unconditionally and is
asserted rather than assumed.

**No float.** Ageing is whole days between two `date`s and every amount is integer minor
units (G1, R10.11). Nothing here divides, so there is no rounding step to get wrong.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.money import minor_to_text
from app.db.explain import Explained, Input, SourceRecord
from app.modules.customers.repository import CustomerRepository
from app.modules.finance.ledger import open_bills, open_invoices, today
from app.modules.finance.schemas import (
    AR_AGE_BUCKETS,
    CURRENT_BUCKET,
    AgeingBucketTotal,
    AgeingPartyRow,
    AgeingReport,
    CollectionsEntry,
    OpenDocument,
    PaymentsDueEntry,
)
from app.modules.suppliers.repository import SupplierRepository

BUCKET_LABELS: dict[str, str] = {key: label for key, label, _upper in AR_AGE_BUCKETS}

#: How many invoices a collections entry links to before it stops listing them. G11 wants
#: the records it reasoned from; a customer with 40 open invoices wants the oldest few.
_RECORD_LIMIT = 5


def bucket_boundaries() -> list[dict[str, str]]:
    """The buckets as the screen prints them (R10.5, R10.6).

    Rendered on the ageing page so the boundaries are *stated*, not inferred from where
    rows happen to land — the same reason `AGE_BUCKETS` is printed on the stock-ageing
    screen. The wording spells out the inclusive upper bound, which is the whole of R10.6.
    """
    out = []
    lower = None
    for key, label, upper in AR_AGE_BUCKETS:
        if upper == 0:
            rule = "due date is today or later — due today is NOT overdue"
        elif upper is None:
            rule = f"more than {lower} days past the due date"
        else:
            rule = f"{(lower or 0) + 1} to {upper} days past the due date, {upper} included"
        out.append({"key": key, "label": label, "rule": rule})
        lower = upper
    return out


class AgeingService:
    """Outstanding money, aged, and the two work lists that come out of it."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.customers = CustomerRepository(db)
        self.suppliers = SupplierRepository(db)

    # --- R10.5: ageing with a due-vs-overdue split ------------------------
    def ar_ageing(self, *, as_of: date | None = None) -> AgeingReport:
        """Receivables by party, aged (R10.5). Four queries plus three grouped sums."""
        stamp = as_of or today()
        docs = open_invoices(self.db, as_of=stamp)
        totals = {pid: amount for pid, amount in self.customers.outstanding_by_customer().items()}
        names = {doc.party_id: (doc.party_name or "—") for doc in docs}
        for pid in totals:
            if pid not in names:
                customer = self.customers.get(pid)
                if customer is not None:
                    names[pid] = customer.name
        return self._report(
            side="receivable",
            as_of=stamp,
            docs=docs,
            totals=totals,
            names=names,
            href="/customers/{id}",
            ledger_href="/finance/ledger?customer_id={id}",
        )

    def ap_ageing(self, *, as_of: date | None = None) -> AgeingReport:
        """Payables by vendor, aged — the same buckets, the same split (R10.5)."""
        stamp = as_of or today()
        docs = open_bills(self.db, as_of=stamp)
        totals = {pid: amount for pid, amount in self.suppliers.outstanding_by_supplier().items()}
        names = {doc.party_id: (doc.party_name or "—") for doc in docs}
        for pid in totals:
            if pid not in names:
                supplier = self.suppliers.get(pid)
                if supplier is not None:
                    names[pid] = supplier.name
        return self._report(
            side="payable",
            as_of=stamp,
            docs=docs,
            totals=totals,
            names=names,
            href="/suppliers/{id}",
            ledger_href="/finance/ledger?side=payable&supplier_id={id}",
        )

    def _report(
        self,
        *,
        side: str,
        as_of: date,
        docs: list[OpenDocument],
        totals: dict[uuid.UUID, int],
        names: dict[uuid.UUID, str],
        href: str,
        ledger_href: str,
    ) -> AgeingReport:
        by_party: dict[uuid.UUID, list[OpenDocument]] = {}
        for doc in docs:
            by_party.setdefault(doc.party_id, []).append(doc)

        rows: list[AgeingPartyRow] = []
        for party_id in set(by_party) | {pid for pid, amount in totals.items() if amount}:
            party_docs = by_party.get(party_id, [])
            buckets = {key: 0 for key, _l, _u in AR_AGE_BUCKETS}
            for doc in party_docs:
                buckets[doc.bucket] += doc.open_minor
            aged = sum(buckets.values())
            outstanding = totals.get(party_id, aged)
            oldest = max(party_docs, key=lambda d: d.days_overdue, default=None)
            rows.append(
                AgeingPartyRow(
                    party_id=party_id,
                    party_name=names.get(party_id, "—"),
                    href=href.format(id=party_id),
                    ledger_href=ledger_href.format(id=party_id),
                    outstanding_minor=outstanding,
                    due_minor=buckets[CURRENT_BUCKET],
                    overdue_minor=aged - buckets[CURRENT_BUCKET],
                    # The residual, by definition — see the module docstring.
                    unaged_minor=outstanding - aged,
                    buckets=buckets,
                    open_count=len(party_docs),
                    oldest_days_overdue=oldest.days_overdue if oldest else None,
                    oldest_doc_no=oldest.doc_no if oldest else None,
                )
            )

        # Biggest overdue first — the screen's job is to put the worst at the top. Ties
        # break on the party name so the order is deterministic on equal money.
        rows.sort(key=lambda r: (-r.overdue_minor, -r.outstanding_minor, r.party_name))

        bucket_totals = [
            AgeingBucketTotal(
                key=key,
                label=label,
                total_minor=sum(r.buckets.get(key, 0) for r in rows),
                count=sum(1 for d in docs if d.bucket == key),
            )
            for key, label, _upper in AR_AGE_BUCKETS
        ]
        return AgeingReport(
            side=side,
            as_of=as_of,
            buckets=bucket_totals,
            rows=rows,
            total_minor=sum(r.outstanding_minor for r in rows),
            due_minor=sum(r.due_minor for r in rows),
            overdue_minor=sum(r.overdue_minor for r in rows),
            unaged_minor=sum(r.unaged_minor for r in rows),
        )

    # --- R10.7: who to chase today ----------------------------------------
    def collections(self, *, as_of: date | None = None) -> list[CollectionsEntry]:
        """The chase list, in priority order, with a reason on every entry (R10.7).

        **Priority is the age of the oldest overdue invoice, then the overdue amount.**
        Age first rather than money first: a small balance that has been ignored for 90
        days is a collection problem, while a large one that fell due yesterday is not yet
        a problem at all. The ordering is fully deterministic — after age and amount it
        breaks on the party name and then the id, so two identical positions cannot swap
        between page loads.

        Only parties with money actually *overdue* appear. A customer who owes a great
        deal, none of it yet due, is not someone to chase today, and putting them on the
        list would make the list something the founder learns to ignore.
        """
        stamp = as_of or today()
        docs = open_invoices(self.db, as_of=stamp)
        by_party: dict[uuid.UUID, list[OpenDocument]] = {}
        for doc in docs:
            by_party.setdefault(doc.party_id, []).append(doc)
        totals = self.customers.outstanding_by_customer()

        entries: list[CollectionsEntry] = []
        for party_id, party_docs in by_party.items():
            overdue = [doc for doc in party_docs if doc.is_overdue]
            if not overdue:
                continue
            overdue.sort(key=lambda d: (-d.days_overdue, d.doc_no))
            oldest = overdue[0]
            overdue_minor = sum(doc.open_minor for doc in overdue)
            outstanding = totals.get(party_id, sum(d.open_minor for d in party_docs))
            name = oldest.party_name or "—"

            reason = (
                f"{minor_to_text(overdue_minor)} overdue — {oldest.doc_no} is "
                f"{oldest.days_overdue} days past its due date of "
                f"{oldest.due_date.isoformat()}"
            )
            if len(overdue) > 1:
                reason += f", oldest of {len(overdue)} overdue invoices"
            if oldest.due_date_assumed:
                reason += " (no payment terms recorded — due on issue)"

            entries.append(
                CollectionsEntry(
                    customer_id=party_id,
                    customer_name=name,
                    href=f"/customers/{party_id}",
                    ledger_href=f"/finance/ledger?customer_id={party_id}",
                    outstanding_minor=outstanding,
                    overdue_minor=overdue_minor,
                    oldest_days_overdue=oldest.days_overdue,
                    oldest_doc_no=oldest.doc_no,
                    oldest_doc_href=oldest.href,
                    open_count=len(party_docs),
                    reason=reason,
                    explained=self._explain_entry(
                        name=name,
                        as_of=stamp,
                        overdue=overdue,
                        overdue_minor=overdue_minor,
                        outstanding=outstanding,
                        open_count=len(party_docs),
                    ),
                )
            )

        entries.sort(
            key=lambda e: (
                -e.oldest_days_overdue,
                -e.overdue_minor,
                e.customer_name,
                str(e.customer_id),
            )
        )
        return entries

    @staticmethod
    def _explain_entry(
        *,
        name: str,
        as_of: date,
        overdue: list[OpenDocument],
        overdue_minor: int,
        outstanding: int,
        open_count: int,
    ) -> Explained:
        """G11 for one chase-list entry: the inputs, the rule, the window, the records.

        A collections list is a recommendation — it tells the founder what to do next — so
        it owes G11 an explanation, and gets the ONE implementation of that shape rather
        than a second one.
        """
        oldest = overdue[0]
        return Explained(
            what=f"Why {name} is on today's chase list",
            value=minor_to_text(overdue_minor),
            formula=(
                "Overdue = Σ open balance of invoices past their due date, where open is "
                "invoice total − payments applied − credit notes. Ranked by the days "
                "overdue on the oldest such invoice, then by the overdue amount. An "
                "invoice due today is not overdue."
            ),
            window=(
                f"{len(overdue)} overdue of {open_count} open invoices, as of "
                f"{as_of.isoformat()}"
            ),
            inputs=(
                Input(label="Oldest overdue invoice", value=f"{oldest.days_overdue} days"),
                Input(label="Overdue", value=minor_to_text(overdue_minor)),
                Input(label="Total outstanding", value=minor_to_text(outstanding)),
                Input(label="Open invoices", value=str(open_count)),
            ),
            records=tuple(
                SourceRecord(
                    label=f"{doc.doc_no} · {minor_to_text(doc.open_minor)} · "
                    f"{doc.days_overdue}d overdue",
                    href=doc.href,
                )
                for doc in overdue[:_RECORD_LIMIT]
            ),
            caveat=(
                f"{len(overdue) - _RECORD_LIMIT} further overdue invoices not listed here"
                if len(overdue) > _RECORD_LIMIT
                else None
            ),
        )

    # --- R10.8: the payable-side work list --------------------------------
    def payments_due(self, *, as_of: date | None = None) -> list[PaymentsDueEntry]:
        """Bills to pay, oldest due first (R10.8).

        Per bill rather than per vendor: paying a supplier is done against a document, and
        the founder needs to know *which* bill is about to go late. Ordered by due date,
        then bill number, so it is deterministic.
        """
        stamp = as_of or today()
        docs = open_bills(self.db, as_of=stamp)
        docs.sort(key=lambda d: (d.due_date, d.doc_no))
        return [
            PaymentsDueEntry(
                bill_id=doc.id,
                bill_no=doc.doc_no,
                href=doc.href,
                supplier_id=doc.party_id,
                supplier_name=doc.party_name or "—",
                ledger_href=f"/finance/ledger?side=payable&supplier_id={doc.party_id}",
                due_date=doc.due_date,
                due_date_assumed=doc.due_date_assumed,
                days_overdue=doc.days_overdue,
                bucket=doc.bucket,
                bucket_label=BUCKET_LABELS[doc.bucket],
                open_minor=doc.open_minor,
            )
            for doc in docs
        ]
