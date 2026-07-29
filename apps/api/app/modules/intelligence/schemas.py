"""The shapes the Intelligence Layer renders (R13.3–R13.5, R13.9, R13.10).

**`Figure` and `Alert` are imported from `command_center`, not redefined.** They already
enforce R12.7 (a number with nowhere to drill through will not construct) and R12.8 (an alert
with nothing to click will not construct), which are R13.10's "links to the underlying
records" under a different number. Inventing a parallel pair here would mean two shapes with
one purpose and a second place for those validators to be forgotten — the exact duplication
Part 10 C1 spent a checkpoint removing.

So this module adds only the containers those pieces sit in: a cockpit is a titled group of
figures, a score family is a definition plus a link to the screen that already shows it, and
a brief item is one line of "here is what changed".
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator

from app.db.explain import Explained
from app.modules.command_center.schemas import Alert, AlertRecord, Figure
from app.modules.intelligence.forecast import Forecast

__all__ = [
    "Alert",
    "AlertRecord",
    "BriefItem",
    "Cockpit",
    "Figure",
    "Intelligence",
    "ScoreFamily",
]


class Cockpit(BaseModel):
    """One of R13.5's three: working capital, category, business unit.

    A titled group of `Figure`s and nothing more — the arithmetic belongs to whichever
    service produced the numbers. `note` is where a cockpit says what its figures do NOT
    include, which on the working-capital one is the sentence about cash at bank.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    key: str
    title: str
    figures: list[Figure]
    note: str | None = None
    explained: Explained | None = None


class ScoreFamily(BaseModel):
    """One of R13.3's three score families, consolidated rather than rebuilt.

    Deliberately a *definition and a link*, not a computed number. Each of these scores is
    per-entity — one per customer, supplier or product — so a page that scored all of them to
    show a headline would run the per-row fan-out R12.12 measures and Part 9 already paid for
    once. The screen that owns each score computes it for the entity in front of you; this
    section's job is that all three are findable in one place with their definitions stated.
    """

    key: str
    label: str
    #: Plain-language definition — the same `what` its `Explained` carries.
    what: str
    formula: str
    window: str
    href: str
    #: Which service computes it, printed so nothing here looks invented.
    owner: str

    @field_validator("href")
    @classmethod
    def _must_drill_through(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError(
                f"R13.10: a score family must link to the screen that computes it — "
                f"got href={value!r}"
            )
        return value


class BriefItem(BaseModel):
    """One line of the Morning Brief (R13.9).

    `source` names the service the line came from, because R13.9's requirement is that the
    Brief contains **no new business logic** and the cheapest way to keep that honest is for
    every line to say who computed it. A line that could not name an owner would be a line
    this module invented.
    """

    rank: int
    headline: str
    #: What to do about it, in the owning service's words — not this module's advice.
    why: str
    href: str
    #: "alert" or "forecast" — which section of the page it came from.
    kind: str
    impact_minor: int | None = None
    source: str = ""

    @field_validator("href")
    @classmethod
    def _must_drill_through(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError(f"R13.10: a brief line must link to its records — {value!r}")
        return value


class Intelligence(BaseModel):
    """The whole page, in the order the requirements ask for it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    as_of: date
    window_from: date
    window_to: date

    #: R13.9 — first on the page, because it is the reason to open it.
    brief: list[BriefItem]
    #: R13.7/R13.8 — purchase, sales, cash requirement.
    forecasts: list[Forecast]
    #: R13.4 — dead stock, margin leakage, churn risk. Only the ones that fired.
    radars: list[Alert]
    #: R13.5 — working capital, category performance, business-unit performance.
    cockpits: list[Cockpit]
    #: R13.3 — the three score families, consolidated.
    scores: list[ScoreFamily]

    @property
    def is_empty(self) -> bool:
        """Nothing measurable yet — a fresh install, not a quiet quarter (R12.15's rule).

        The same distinction Part 9 drew and for the same reason: a business with real
        history and no radar firing should see its zeros, because those are measurements. A
        system with nothing in it has no measurements, and three confident ₹0.00 forecasts
        presented as though it did would be the first thing this page got wrong.
        """
        cockpit_figures = [f for c in self.cockpits for f in c.figures]
        return (
            not self.radars
            and all(f.value_minor == 0 for f in self.forecasts)
            and all(f.value in (0, "unknown", "") for f in cockpit_figures)
        )
