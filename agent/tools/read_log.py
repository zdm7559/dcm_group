from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ToolResult = dict[str, Any]

BUG_BLOCK_START = "=== AUTO_FIX_BUG_START ==="
BUG_BLOCK_END = "=== AUTO_FIX_BUG_END ==="
DEFAULT_LOG_PATH = "logs/error.log"
PROJECT_FRAME_MARKER = "/飞书挑战赛/project/"
PROJECT_PATH_ROOTS = ("web_service", "tests", "agent")


def ok(data: Any = None) -> ToolResult:
    return {"ok": True, "data": data, "error": None}


def fail(error: str, data: Any = None) -> ToolResult:
    return {"ok": False, "data": data, "error": error}


def read_error_logs(
    log_path: str | Path = DEFAULT_LOG_PATH,
    *,
    mode: str = "grouped",
    limit: int | None = 20,
) -> ToolResult:
    """Read structured error blocks from the service error log.

    Supported modes:
    - all: return parsed error events in chronological order.
    - latest: return only the latest parsed error event.
    - grouped: merge repeated events by fingerprint.
    """
    path = Path(log_path)
    if not path.exists():
        return fail(f"log file does not exist: {path}")

    content = path.read_text(encoding="utf-8")
    raw_blocks = extract_bug_blocks(content)
    if not raw_blocks:
        return fail("no complete bug block found")

    errors: list[dict[str, Any]] = []
    invalid_blocks: list[dict[str, Any]] = []

    for index, raw_block in enumerate(raw_blocks):
        parsed_result = parse_bug_block(raw_block)
        if not parsed_result["ok"]:
            invalid_blocks.append(
                {
                    "index": index,
                    "error": parsed_result["error"],
                    "raw_block": raw_block,
                }
            )
            continue

        error_event = parsed_result["data"]
        enrich_traceback_context(error_event)
        error_event["fingerprint"] = build_fingerprint(error_event)
        errors.append(error_event)

    if not errors:
        return fail("no valid bug block found", {"invalid_blocks": invalid_blocks})

    if mode == "all":
        selected_errors = _apply_limit(errors, limit)
        return ok(
            {
                "mode": mode,
                "count": len(selected_errors),
                "errors": selected_errors,
                "invalid_blocks": invalid_blocks,
            }
        )

    if mode == "latest":
        latest_error = errors[-1]
        return ok(
            {
                "mode": mode,
                "count": 1,
                "error": latest_error,
                "invalid_blocks": invalid_blocks,
            }
        )

    if mode == "grouped":
        grouped_errors = group_errors_by_fingerprint(errors)
        selected_groups = _apply_limit(grouped_errors, limit)
        return ok(
            {
                "mode": mode,
                "count": len(selected_groups),
                "errors": selected_groups,
                "invalid_blocks": invalid_blocks,
            }
        )

    return fail(f"unsupported read mode: {mode}")


def read_latest_error_log(
    log_path: str | Path = DEFAULT_LOG_PATH,
) -> ToolResult:
    """Read the latest parsed error block from the service error log."""
    return read_error_logs(log_path, mode="latest", limit=1)


def extract_bug_blocks(content: str) -> list[str]:
    pattern = re.compile(
        rf"{re.escape(BUG_BLOCK_START)}\s*(.*?)\s*{re.escape(BUG_BLOCK_END)}",
        re.DOTALL,
    )
    return [match.group(1).strip() for match in pattern.finditer(content)]


def parse_bug_block(raw_block: str) -> ToolResult:
    try:
        error_data = json.loads(raw_block)
    except json.JSONDecodeError as exc:
        return fail(f"bug block is not valid JSON: {exc}", {"raw_block": raw_block})

    if not isinstance(error_data, dict):
        return fail("bug block JSON must be an object", {"raw_block": raw_block})

    return ok(error_data)


def build_fingerprint(error_event: dict[str, Any]) -> str:
    project_frame = error_event.get("suspect_frame") or {}
    fingerprint_source = {
        "exception_type": error_event.get("exception_type"),
        "path": error_event.get("path"),
        "file": project_frame.get("file"),
        "line": project_frame.get("line"),
        "function": project_frame.get("function"),
    }
    raw_fingerprint = json.dumps(
        fingerprint_source,
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()[:16]


def enrich_traceback_context(error_event: dict[str, Any]) -> None:
    project_frames = extract_project_frames(error_event.get("traceback", ""))
    suspect_frame = project_frames[-1] if project_frames else None

    files_to_read = _unique_files_from_frames(reversed(project_frames))

    error_event["project_frames"] = project_frames
    error_event["suspect_frame"] = suspect_frame
    error_event["context_hints"] = {
        "primary_file": suspect_frame["file"] if suspect_frame else None,
        "files_to_read": files_to_read,
    }


def group_errors_by_fingerprint(
    errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    for error_event in errors:
        fingerprint = error_event["fingerprint"]
        if fingerprint not in groups:
            groups[fingerprint] = {
                "fingerprint": fingerprint,
                "occurrences": 0,
                "first_seen": error_event.get("timestamp"),
                "latest_seen": error_event.get("timestamp"),
                "latest": error_event,
            }

        group = groups[fingerprint]
        group["occurrences"] += 1
        group["latest_seen"] = error_event.get("timestamp")
        group["latest"] = error_event

    return sorted(
        groups.values(),
        key=lambda group: (
            group["occurrences"],
            group.get("latest_seen") or "",
        ),
        reverse=True,
    )


def extract_project_frames(traceback_text: str) -> list[dict[str, Any]]:
    frame_pattern = re.compile(
        r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<function>[^\n]+)'
    )
    project_frames = []

    for match in frame_pattern.finditer(traceback_text):
        file_path = match.group("file")
        relative_path = _to_project_relative_path(file_path)
        if relative_path is None:
            continue

        project_frames.append(
            {
                "file": relative_path,
                "line": int(match.group("line")),
                "function": match.group("function"),
            }
        )

    return project_frames


def _to_project_relative_path(file_path: str) -> str | None:
    if PROJECT_FRAME_MARKER in file_path:
        return file_path.split(PROJECT_FRAME_MARKER, 1)[1]

    normalized = file_path.replace("\\", "/")
    for root in PROJECT_PATH_ROOTS:
        if normalized == root or normalized.startswith(f"{root}/"):
            return normalized

    parts = Path(normalized).parts
    for index, part in enumerate(parts):
        if part in PROJECT_PATH_ROOTS:
            return "/".join(parts[index:])

    return None


def _unique_files_from_frames(frames: Any) -> list[str]:
    seen: set[str] = set()
    files: list[str] = []

    for frame in frames:
        file_path = frame.get("file")
        if not file_path or file_path in seen:
            continue
        seen.add(file_path)
        files.append(file_path)

    return files


def _apply_limit(items: list[Any], limit: int | None) -> list[Any]:
    if limit is None:
        return items
    if limit <= 0:
        return []
    return items[-limit:] if len(items) > limit else items
