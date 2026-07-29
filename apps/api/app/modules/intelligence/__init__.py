"""The Intelligence Layer (Part 10) — radars, cockpits, forecasts and the Morning Brief.

**This module owns no entity and holds no arithmetic beyond one trailing average.** Like
`command_center/`, it has no `models.py`, no `repository.py` and no `router.py`: everything it
shows is computed by the part that owns it, and Part 10 C1's audit table records where each of
those 23 outputs lives. The only measurement Part 10 added is customer churn, and it lives in
`customers/churn.py` because customers is the part that owns customers.

Three files:

    forecast.py   the three trailing-window projections (R13.7, R13.8)
    schemas.py    the containers; `Figure`/`Alert` are imported from `command_center`
    service.py    the projection — assembles, never computes

No new model, so nothing is owed to `app/db/references.py` (R3.7) and no column is owed to
`_ADDITIVE_COLUMNS`. That is a property of the design rather than a shortcut: a score the
system worked out must not be stored (G7).
"""
