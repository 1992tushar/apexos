"""Enumerating the web routes, for the walks R1.5 and the smoke tests perform.

FastAPI >= 0.140 no longer flattens `include_router` into the parent's `.routes`:
each inclusion becomes an `_IncludedRouter` wrapper that holds the real router on
`.original_router`. A shallow walk of `build_web_router().routes` therefore yields
19 wrappers with no `.methods` and **zero** routes — which is what silently turned
R1.5's assertion into `[] == []`. Recurse through the wrappers instead.

Page routers are included without a prefix (each page module declares full paths),
so walking the web router cannot pick up a JSON API route by accident.
"""
from __future__ import annotations

from typing import Any

from app.web import build_web_router


def _iter_routes(routes: list[Any]):
    for route in routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _iter_routes(included.routes)
            continue
        nested = getattr(route, "routes", None)
        if nested:
            yield from _iter_routes(nested)
            continue
        if getattr(route, "methods", None):
            yield route


def web_routes() -> list[Any]:
    """Every concrete route the web UI serves."""
    return list(_iter_routes(build_web_router().routes))


def web_routes_for(method: str) -> list[Any]:
    return [r for r in web_routes() if method in r.methods]


def plain_get_paths() -> list[str]:
    """GET paths carrying no path parameter — the ones a walk can request blind."""
    return sorted({r.path for r in web_routes_for("GET") if "{" not in r.path})
