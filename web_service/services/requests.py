from __future__ import annotations

import json


def parse_json_body(raw_body: str) -> dict[str, object]:
    return json.loads(raw_body)
