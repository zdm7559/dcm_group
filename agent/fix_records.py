from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ToolResult = dict[str, Any]


def ok(data: Any = None) -> ToolResult:
    return {"ok": True, "data": data, "error": None}


def fail(error: str, data: Any = None) -> ToolResult:
    return {"ok": False, "data": data, "error": error}


def save_fix_record(
    *,
    error_event: dict[str, Any],
    diagnosis: dict[str, Any] | None,
    write_result: dict[str, Any] | None,
    test_result: dict[str, Any] | None,
    repo_path: str | Path = ".",
    record_dir: str | Path = "fix_records",
) -> ToolResult:
    repo = Path(repo_path)
    output_dir = repo / record_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    error_type = str(error_event.get("exception_type") or "unknown").lower()
    fingerprint = str(error_event.get("fingerprint") or "no-fingerprint")
    record_path = output_dir / f"{timestamp}-{error_type}-{fingerprint}.md"

    record_path.write_text(
        _render_record(
            error_event=error_event,
            diagnosis=diagnosis,
            write_result=write_result,
            test_result=test_result,
        ),
        encoding="utf-8",
    )

    return ok({"path": str(record_path)})


def _render_record(
    *,
    error_event: dict[str, Any],
    diagnosis: dict[str, Any] | None,
    write_result: dict[str, Any] | None,
    test_result: dict[str, Any] | None,
) -> str:
    test_data = test_result.get("data") if test_result else None
    write_data = write_result.get("data") if write_result else None

    return "\n".join(
        [
            "# AutoFix Record",
            "",
            "## Error",
            "",
            f"- Type: `{error_event.get('exception_type')}`",
            f"- Path: `{error_event.get('path')}`",
            f"- Fingerprint: `{error_event.get('fingerprint')}`",
            f"- Suspect: `{error_event.get('suspect_frame')}`",
            "",
            "## Diagnosis",
            "",
            "```json",
            json.dumps(diagnosis or {}, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Write Result",
            "",
            "```json",
            json.dumps(write_data or {}, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Test Result",
            "",
            f"- Passed: `{test_data.get('passed') if test_data else None}`",
            f"- Exit Code: `{test_data.get('exit_code') if test_data else None}`",
            "",
            "```text",
            test_data.get("summary", "") if test_data else "",
            "```",
            "",
        ]
    )
