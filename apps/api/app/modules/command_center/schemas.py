"""The shapes the Command Center renders (R12.1–R12.9).

Four types and one container. They are deliberately dumb: every value arrives already
computed by the part that owns it, and the only logic here is the two validators that
make R12.7 and R12.8 structural rather than a review note —

* a `Figure` cannot exist without an `href`, so "every number drills through" cannot be
  forgotten on a tile someone adds in six months, and
* an `Alert` cannot exist without records, so "an alert with nothing to click MUST be
  removed" is enforced by the constructor instead of by a screen review.

The second one matters more than it looks. R11.8 asked the same thing of Part 8's
leakage indicators and the honest answer there was to *not build* the indicator whose
data does not exist. The same applies here: a service that finds nothing to alert about
omits the alert entirely, and the page says "nothing needs attention" — which is
information — rather than showing a row of confident zeros, which is not.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.db.explain import Explained


class Figure(BaseModel):
    """One number on the page, and where its rows live (R12.7).

    `kind` drives formatting in the template exactly as `Column.kind` does for lists —
    the service never formats and the template never computes. `hint` is the one line of
    context that makes the figure a decision rather than a fact: what is overdue inside
    the receivable, how many products have no cost behind the inventory value.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    key: str
    label: str
    #: money | count | text — matches the `money` / `number` Jinja filters.
    kind: str
    value: int | str
    #: R12.7. Never empty: the validator below refuses a tile with nowhere to go.
    href: str
    hint: str | None = None
    explained: Explained | None = None

    @field_validator("href")
    @classmethod
    def _must_drill_through(cls, value: str) -> str:
        if not value or not value.startswith("/"):
            raise ValueError(
                "R12.7: every number must drill through to the rows behind it — "
                f"this figure has href={value!r}"
            )
        return value

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, value: str) -> str:
        if value not in ("money", "count", "text"):
            raise ValueError(f"unknown figure kind {value!r}")
        return value


class AlertRecord(BaseModel):
    """One affected record, with the link R12.8 requires."""

    label: str
    href: str
    detail: str | None = None


class Alert(BaseModel):
    """Something that needs attention, stated so it can be checked (R12.8).

    `trigger` is what happened, `threshold` is the line it crossed, and `records` are the
    rows it happened to. All three are printed; none is optional. `impact_minor` is set
    only where the alert has a money consequence its own owner measured — it is never
    summed across alerts, for the reason Part 8's C3 removed a tile that did exactly
    that: a loss and a give-away added together read as a loss nobody made.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    key: str
    label: str
    trigger: str
    threshold: str
    #: How many records fired, which may exceed `len(records)` when the list is capped.
    count: int
    records: list[AlertRecord]
    #: The full list this alert is a summary of.
    href: str
    impact_minor: int | None = None
    explained: Explained | None = None
    #: Which part owns the rule — printed, so the founder can see nothing is invented here.
    source: str = ""

    @model_validator(mode="after")
    def _must_have_something_to_click(self) -> Alert:
        if not self.records:
            raise ValueError(
                f"R12.8: the alert {self.key!r} has nothing to click and must not be "
                "built. Omit it — an empty alert is noise, not a clean result."
            )
        if self.count < len(self.records):
            raise ValueError(
                f"alert {self.key!r} reports {self.count} records but carries "
                f"{len(self.records)} — the count must not understate the list"
            )
        return self

    @property
    def hidden_count(self) -> int:
        """Records the alert found but is not showing, so the cap is never silent."""
        return max(self.count - len(self.records), 0)


class QuickAction(BaseModel):
    """One of R12.6's four most frequent tasks."""

    label: str
    href: str
    #: Why this is one of the four. Kept on screen so a fifth has to argue for itself.
    why: str


class ActivityEntry(BaseModel):
    """One `activity_log` row as the feed shows it (R12.5)."""

    verb: str
    entity_type: str
    summary: str
    occurred_at: object


class CommandCenter(BaseModel):
    """The whole page, in R12.1's order.

    The three questions are three fields, in the order they are asked. `position` and
    `activity` both answer "what happened" — one as a balance, one as a log — and
    `actions` is the entire answer to "what should I do now", because everything else on
    the page already links to the thing to do.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    as_of: date
    #: The window `position` and the leakage alert were computed over (R11.13).
    window_from: date
    window_to: date

    # 1 — what happened
    happened: list[Figure]
    #: How thin today's sample is. Present whenever "today" is one document or two, for
    #: the reason Part 8 marks a 10,000-day DIO: correct, and useless read as precise.
    happened_caveat: str | None = None
    position: list[Figure]
    position_caveat: str | None = None

    # 2 — what needs attention
    attention: list[Figure]
    alerts: list[Alert]

    # 3 — what should I do now
    actions: list[QuickAction]

    activity: list[ActivityEntry]

    @property
    def alert_count(self) -> int:
        return sum(a.count for a in self.alerts)

    @property
    def is_empty(self) -> bool:
        """Nothing has ever been recorded — a fresh install, not a quiet day (R12.15).

        **The distinction is the whole point.** A business with a hundred invoices and
        nothing falling due today should see its zeros, because those zeros are
        measurements. A system that has never been used has no measurements at all, and
        twelve confident ₹0.00 tiles presented as though it did would be the first thing
        this page got wrong — the same objection G11 makes to reporting 0 for a score that
        cannot be computed.

        Three conditions, because any one alone is reachable on a live system: an empty
        `activity_log` (G5 writes exactly one row per state change, so it is the most
        reliable "nothing has happened" signal), no alert fired, and no figure carrying a
        value. It says nothing about *why* — the template's banner says only that the
        figures will fill in, which is all anyone can honestly claim.
        """
        figures = self.happened + self.position + self.attention
        return (
            not self.activity
            and not self.alerts
            and all(f.value in (0, "unknown", "") for f in figures)
        )
