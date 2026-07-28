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


def minor_to_text(minor: int | None) -> str:
    """Integer minor units as an exact decimal string.

    `123456` -> `"1234.56"`; `-50` -> `"-0.50"`; `None` -> `"0.00"`.
    """
    value = int(minor or 0)
    sign = "-" if value < 0 else ""
    units, sub = divmod(abs(value), 100)
    return f"{sign}{units}.{sub:02d}"
