"""One shape for every explained number (G11).

G11 is P0 and applies to *every* score, rate, recommendation and forecast the
product shows: each must render its inputs, its formula, the data window it used,
and links to the records it reasoned from — and must say **"unknown"** rather than
invent a misleading default like 0 or 50 when it cannot be computed.

That is the same four-part shape every time. Part 4 alone has four of them (vendor
score, measured lead time, on-time rate, purchase recommendation), and parts 5, 7,
8, 9 and 10 add more — inventory health, customer health, margin, forecasts. So it
is defined once here and rendered by one macro (`explain_panel` in `_macros.html`),
rather than each screen inventing its own way to show the arithmetic.

`Explained.unknown(...)` is the insufficient-data case (R5.11). It carries the
reason instead of a value and `.is_known` is False, so a caller cannot accidentally
render a number that does not exist.

This module is pure: no session, no models, no queries. Services build `Explained`;
templates render it.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Input:
    """One term that fed the formula, as it should read on screen."""

    label: str
    value: str
    #: How much this term contributed, e.g. "60%". None for an unweighted input.
    weight: str | None = None
    #: Why this term is missing, when it is. Set with `value=""`.
    missing_reason: str | None = None

    @property
    def is_missing(self) -> bool:
        return self.missing_reason is not None


@dataclass(frozen=True)
class SourceRecord:
    """A record the number was computed from — G11's "links to the records"."""

    label: str
    href: str | None = None


@dataclass(frozen=True)
class Explained:
    """A number plus everything G11 requires to be shown next to it.

    `value` is the *rendered* value (services format it; templates never compute).
    `value is None` means unknown, and `unknown_reason` then says why.
    """

    #: Plain-language definition — what this number means.
    what: str
    #: The rendered value, or None when it cannot be computed.
    value: str | None
    #: The arithmetic, in a form the founder can redo by hand.
    formula: str
    #: The data window the inputs came from, e.g. "6 receipts, 2026-03-02 to 2026-07-11".
    window: str
    inputs: tuple[Input, ...] = ()
    records: tuple[SourceRecord, ...] = ()
    unknown_reason: str | None = None
    #: Optional caveat shown with the value — a measured-vs-promised gap, a small sample.
    caveat: str | None = None

    @property
    def is_known(self) -> bool:
        return self.value is not None

    @property
    def display(self) -> str:
        """What the screen shows — never a stand-in number (G11)."""
        return self.value if self.value is not None else "unknown"

    @classmethod
    def unknown(
        cls,
        *,
        what: str,
        formula: str,
        reason: str,
        window: str = "no data",
        inputs: tuple[Input, ...] = (),
        records: tuple[SourceRecord, ...] = (),
    ) -> Explained:
        """The insufficient-history case (R5.11).

        Still carries the formula and the window, because "here is what I would
        need in order to tell you" is the useful half of an unknown.
        """
        return cls(
            what=what,
            value=None,
            formula=formula,
            window=window,
            inputs=inputs,
            records=records,
            unknown_reason=reason,
        )


@dataclass
class ExplainedSet:
    """Several explained numbers shown together, e.g. one supplier's intelligence."""

    items: list[Explained] = field(default_factory=list)

    def add(self, item: Explained) -> Explained:
        self.items.append(item)
        return item

    @property
    def known(self) -> list[Explained]:
        return [i for i in self.items if i.is_known]

    @property
    def all_unknown(self) -> bool:
        return bool(self.items) and not self.known
