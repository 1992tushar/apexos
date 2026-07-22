"""UUID v7 generator (time-ordered) — decision D6 in the canonical foundation.

UUID v7 embeds a 48-bit Unix-millisecond timestamp in the high bits, so primary
keys sort by creation time while remaining globally unique and opaque.
"""
from __future__ import annotations

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    """Generate a UUID version 7 (RFC 9562)."""
    unix_ms = time.time_ns() // 1_000_000
    ts = unix_ms.to_bytes(6, "big")
    rand = bytearray(os.urandom(10))
    b = bytearray(ts) + rand
    b[6] = (b[6] & 0x0F) | 0x70  # version 7
    b[8] = (b[8] & 0x3F) | 0x80  # variant 10
    return uuid.UUID(bytes=bytes(b))
