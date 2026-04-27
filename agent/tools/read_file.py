from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Iterable


ToolResult = dict[str, Any]
DEFAULT_CONTEXT_LINES = 30
DEFAULT_MAX_LINES = 160


def ok(data: Any = None) -> ToolResult:
    return {"ok": True, "data": data, "error": None}


def fail(error: str, data: Any = None) -> ToolResult:
    return {"ok": False, "data": data, "error": error}


def read_file(
    path: str | Path,
    *,
    line: int | None = None,
    function: str | None = None,
    repo_path: str | Path = ".",
    context_lines: int = DEFAULT_CONTEXT_LINES,
    max_lines: int = DEFAULT_MAX_LINES,
) -> ToolResult:
    """Read the most relevant source block from one file."""
    resolved_path = _resolve_repo_path(path, repo_path)
    display_path = str(path)

    if not resolved_path.exists():
        return fail(
            f"file does not exist: {display_path}",
            _missing_file_payload(display_path),
        )
    if not resolved_path.is_file():
        return fail(
            f"path is not a file: {display_path}",
            _missing_file_payload(display_path),
        )

    try:
        source = resolved_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return fail(f"file is not valid utf-8: {display_path}: {exc}")

    lines = source.splitlines()
    total_lines = len(lines)

    if line is not None and (line < 1 or line > max(total_lines, 1)):
        return fail(
            f"line is out of range for {display_path}: {line}",
            {
                "path": display_path,
                "exists": True,
                "total_lines": total_lines,
            },
        )

    node_range = _find_ast_node_range(source, line) if line is not None else None
    if node_range:
        line_start, line_end, symbol = node_range
        payload = _build_payload(
            path=display_path,
            lines=lines,
            line_start=line_start,
            line_end=line_end,
            total_lines=total_lines,
            read_mode="function",
            target_line=line,
            target_function=function,
            symbol=symbol,
            max_lines=max_lines,
            context_lines=context_lines,
        )
        return ok(payload)

    if line is not None:
        line_start = max(1, line - context_lines)
        line_end = min(total_lines, line + context_lines)
        payload = _build_payload(
            path=display_path,
            lines=lines,
            line_start=line_start,
            line_end=line_end,
            total_lines=total_lines,
            read_mode="line_window",
            target_line=line,
            target_function=function,
            symbol=None,
            max_lines=max_lines,
            context_lines=context_lines,
        )
        return ok(payload)

    payload = _build_payload(
        path=display_path,
        lines=lines,
        line_start=1,
        line_end=total_lines,
        total_lines=total_lines,
        read_mode="full_file",
        target_line=None,
        target_function=function,
        symbol=None,
        max_lines=max_lines,
        context_lines=context_lines,
    )
    return ok(payload)


def read_files(
    files: list[dict[str, Any] | str | Path],
    *,
    repo_path: str | Path = ".",
    context_lines: int = DEFAULT_CONTEXT_LINES,
    max_lines: int = DEFAULT_MAX_LINES,
) -> ToolResult:
    """Read multiple files or frame-like objects."""
    results = []
    failures = []

    for item in files:
        file_request = _normalize_file_request(item)
        result = read_file(
            file_request["path"],
            line=file_request.get("line"),
            function=file_request.get("function"),
            repo_path=repo_path,
            context_lines=context_lines,
            max_lines=max_lines,
        )
        if result["ok"]:
            results.append(result["data"])
        else:
            failures.append(
                {
                    "path": file_request["path"],
                    "error": result["error"],
                    "data": result["data"],
                }
            )

    if not results:
        return fail("failed to read all requested files", {"files": [], "failures": failures})

    return ok(
        {
            "count": len(results),
            "files": results,
            "failures": failures,
        }
    )


def read_files_for_error(
    error_event: dict[str, Any],
    *,
    repo_path: str | Path = ".",
    include_tests: bool = True,
    context_lines: int = DEFAULT_CONTEXT_LINES,
    max_lines: int = DEFAULT_MAX_LINES,
) -> ToolResult:
    """Read source blocks suggested by one read_log error event."""
    frame_by_file = {
        frame["file"]: frame
        for frame in error_event.get("project_frames", [])
        if frame.get("file")
    }
    files_to_read = list(error_event.get("context_hints", {}).get("files_to_read", []))

    requests: list[dict[str, Any]] = []
    for file_path in files_to_read:
        frame = frame_by_file.get(file_path, {})
        requests.append(
            {
                "path": file_path,
                "line": frame.get("line"),
                "function": frame.get("function"),
            }
        )

    if include_tests:
        requests.append({"path": "tests/test_service.py"})

    requests = _dedupe_file_requests(requests)
    if not requests:
        return fail("error event does not contain files to read")

    result = read_files(
        requests,
        repo_path=repo_path,
        context_lines=context_lines,
        max_lines=max_lines,
    )
    if not result["ok"]:
        return result

    result["data"]["source"] = {
        "path": error_event.get("path"),
        "exception_type": error_event.get("exception_type"),
        "fingerprint": error_event.get("fingerprint"),
    }
    return result


def _resolve_repo_path(path: str | Path, repo_path: str | Path) -> Path:
    file_path = Path(path)
    if file_path.is_absolute():
        return file_path
    return Path(repo_path) / file_path


def _find_ast_node_range(source: str, line: int | None) -> tuple[int, int, str] | None:
    if line is None:
        return None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    candidates: list[tuple[int, int, str]] = []
    node_types = (ast.FunctionDef, ast.AsyncFunctionDef)

    for node in ast.walk(tree):
        if not isinstance(node, node_types):
            continue
        end_lineno = getattr(node, "end_lineno", None)
        if end_lineno is None:
            continue
        if node.lineno <= line <= end_lineno:
            candidates.append((node.lineno, end_lineno, node.name))

    if not candidates:
        return None

    return min(candidates, key=lambda item: item[1] - item[0])


def _build_payload(
    *,
    path: str,
    lines: list[str],
    line_start: int,
    line_end: int,
    total_lines: int,
    read_mode: str,
    target_line: int | None,
    target_function: str | None,
    symbol: str | None,
    max_lines: int,
    context_lines: int,
) -> dict[str, Any]:
    truncated = False
    original_line_start = line_start
    original_line_end = line_end

    if max_lines > 0 and line_end - line_start + 1 > max_lines:
        truncated = True
        if target_line is not None:
            half_window = max_lines // 2
            line_start = max(1, target_line - half_window)
            line_end = min(total_lines, line_start + max_lines - 1)
            line_start = max(1, line_end - max_lines + 1)
        else:
            line_end = min(total_lines, line_start + max_lines - 1)

    content = "\n".join(lines[line_start - 1 : line_end])

    return {
        "path": path,
        "exists": True,
        "read_mode": read_mode,
        "symbol": symbol,
        "target_line": target_line,
        "target_function": target_function,
        "line_start": line_start,
        "line_end": line_end,
        "total_lines": total_lines,
        "truncated": truncated,
        "original_line_start": original_line_start,
        "original_line_end": original_line_end,
        "context_lines": context_lines,
        "max_lines": max_lines,
        "content": content,
    }


def _normalize_file_request(item: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(item, dict):
        return {
            "path": item["path"],
            "line": item.get("line"),
            "function": item.get("function"),
        }

    return {"path": str(item), "line": None, "function": None}


def _dedupe_file_requests(requests: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for request in requests:
        path = request.get("path")
        if not path or path in seen:
            continue
        seen.add(path)
        deduped.append(request)

    return deduped


def _missing_file_payload(path: str) -> dict[str, Any]:
    return {
        "path": path,
        "exists": False,
        "read_mode": None,
        "content": "",
    }
