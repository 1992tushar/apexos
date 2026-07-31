"""GST tax-invoice print view (Part 13, R16.x).

A print/download document is a different SHAPE from the invoice dashboard
(`finance/invoice.html`) — a legal seller block, a buyer block, HSN per line, and the
CGST/SGST/IGST split a tax invoice must show — not a second invoice implementation.
Every figure here is read from the same `Invoice`/`InvoiceLine` rows `InvoiceService`
already projects; this module stores nothing new (G7). The tax split is derived at
print time by comparing state codes rather than stored per line (R16.3), so a
correction to either party's registered state is reflected on the next print rather
than requiring a re-issued invoice.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.config.service import CompanyProfileService
from app.modules.customers.models import Customer
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import InvoicePrintLine, InvoicePrintView
from app.modules.products.models import Product


def _state_code(gstin: str | None) -> str | None:
    """The state code embedded in a GSTIN's first two digits.

    Fixed by the GST Council's numbering scheme, so this needs no second lookup table
    and cannot drift from a party's own registered GSTIN. Returns `None` for an absent
    or malformed GSTIN — most often an unregistered/B2C customer.
    """
    if gstin and len(gstin) >= 2 and gstin[:2].isdigit():
        return gstin[:2]
    return None


class InvoicePrintService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = FinanceRepository(db)

    def get(self, invoice_id: uuid.UUID) -> InvoicePrintView:
        inv = self.repo.get(invoice_id)
        if inv is None:
            raise NotFoundError(f"Invoice {invoice_id} not found")
        company = CompanyProfileService(self.db).get()
        customer = self.db.get(Customer, inv.customer_id)

        company_state_code = _state_code(company.gstin) or company.state_code
        customer_state_code = _state_code(customer.gstin) if customer else None
        # Neither GSTIN carries a usable state prefix (the common case for an
        # unregistered/B2C customer) — same-state is ASSUMED rather than left
        # unresolved, because most of this book of business is local. The assumption
        # is stated on the printed page rather than silently baked into the split
        # with nothing to show for it (G11).
        state_assumed = customer_state_code is None
        same_state = (
            state_assumed
            or company_state_code is None
            or customer_state_code == company_state_code
        )

        lines: list[InvoicePrintLine] = []
        for ln in inv.lines:
            product = self.db.get(Product, ln.product_id)
            if same_state:
                cgst_minor = ln.line_tax_minor // 2
                sgst_minor = ln.line_tax_minor - cgst_minor
                igst_minor = 0
                cgst_bps = sgst_bps = ln.tax_rate_bps // 2
                igst_bps = 0
            else:
                cgst_minor = sgst_minor = 0
                igst_minor = ln.line_tax_minor
                cgst_bps = sgst_bps = 0
                igst_bps = ln.tax_rate_bps
            lines.append(
                InvoicePrintLine(
                    line_no=ln.line_no,
                    product_name=product.name if product else "—",
                    hsn_code=product.hsn_code if product else None,
                    qty=ln.qty,
                    unit_price_minor=ln.unit_price_minor,
                    taxable_minor=ln.line_subtotal_minor,
                    cgst_bps=cgst_bps,
                    sgst_bps=sgst_bps,
                    igst_bps=igst_bps,
                    cgst_minor=cgst_minor,
                    sgst_minor=sgst_minor,
                    igst_minor=igst_minor,
                    line_total_minor=ln.line_total_minor,
                )
            )

        return InvoicePrintView(
            id=inv.id,
            invoice_no=inv.invoice_no,
            invoice_date=inv.invoice_date,
            due_date=inv.due_date,
            company_legal_name=company.legal_name,
            company_address_line1=company.address_line1,
            company_address_line2=company.address_line2,
            company_city=company.city,
            company_state=company.state,
            company_pincode=company.pincode,
            company_gstin=company.gstin,
            company_pan=company.pan,
            company_phone=company.phone,
            company_email=company.email,
            company_bank_name=company.bank_name,
            company_bank_account_no=company.bank_account_no,
            company_bank_ifsc=company.bank_ifsc,
            company_signatory_name=company.signatory_name,
            company_is_placeholder=company.is_placeholder,
            customer_name=customer.name if customer else "—",
            customer_gstin=customer.gstin if customer else None,
            customer_billing_address=customer.billing_address if customer else None,
            customer_city=customer.city if customer else None,
            customer_state=customer.state if customer else None,
            same_state=same_state,
            state_assumed=state_assumed,
            lines=lines,
            subtotal_minor=inv.subtotal_minor,
            tax_minor=inv.tax_minor,
            cgst_total_minor=sum(ln.cgst_minor for ln in lines),
            sgst_total_minor=sum(ln.sgst_minor for ln in lines),
            igst_total_minor=sum(ln.igst_minor for ln in lines),
            total_minor=inv.total_minor,
        )
