"""Money as text, without ever touching a float (G1).

Money is stored and computed as integer minor units everywhere. Two places need
it as a *plain* decimal string rather than a display string: the CSV export
(Excel wants `1234.56`, not `₹1,234.56`) and the change-history panel (a
`*_minor` field's before/after). This is the one conversion both use, and it is
integer arithmetic end to end — `minor / 100` would introduce a float into a
money path, which G1 forbids.

`app.web.core.money` is a different job: it *presents* a figure with the rupee
symbol and Indian digit grouping. This module produces the machine-readable form.
"""
from __future__ import annotations

from decimal import Decimal


def qty_text(value: Decimal) -> str:
    """A quantity as a person would write it: 40, not 40.0000.

    `Numeric(18, 4)` reads back at full scale, which is right for arithmetic and wrong in
    a sentence. The web layer's `number` filter does this for screens, but a service
    message cannot import `app.web` (it would invert the layering — Part 2 decision 10),
    so the rule lives here. Plain `.normalize()` is not enough: it turns 40 into `4E+1`.

    Lived in `procurement/service.py` until Part 5 C1, when the reservation refusals
    needed it too. Inventory cannot import procurement — procurement imports
    `InventoryService`, so that would be circular — and a second copy would be a second
    implementation of the same rule (G16), which is exactly what this codebase does not do.
    """
    value = Decimal(value)
    tidy = value.quantize(Decimal(1)) if value == value.to_integral_value() else value.normalize()
    return format(tidy, "f")


def minor_to_text(minor: int | None) -> str:
    """Integer minor units as an exact decimal string.

    `123456` -> `"1234.56"`; `-50` -> `"-0.50"`; `None` -> `"0.00"`.
    """
    value = int(minor or 0)
    sign = "-" if value < 0 else ""
    units, sub = divmod(abs(value), 100)
    return f"{sign}{units}.{sub:02d}"
