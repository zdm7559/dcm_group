from __future__ import annotations

import os


def read_required_api_key() -> str:
    return os.environ["API_KEY"]


def read_timeout_seconds() -> int:
    return int(os.getenv("TIMEOUT", "abc"))
