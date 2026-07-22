"""Fulfillment router — no public endpoints in the spine (fulfillment is created
via POST /sales-orders/{id}/fulfill). Exists so api.py can load it."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["fulfillment"])
