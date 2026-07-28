"""`python -m app.seed` entry point."""
from __future__ import annotations

import json

from app.seed import run

if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
