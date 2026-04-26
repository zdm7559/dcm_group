from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


ToolResult = dict[str, Any]
BLOCKED_PATH_PARTS = {".git", "__pycache__", ".pytest_cache"}
BLOCKED_FILE_NAMES = {".env"}
BLOCKED_RELATIVE_PATHS = {"logs/error.log"}


def ok(data: Any = None) -> ToolResult:
    return {"ok": True, "data": data, "error": None}


def fail(error: str, data: Any = None) -> ToolResult:
    return {"ok": False, "data": data, "error": error}


def replace_in_file(
    path: str | Path,
    old_text: str,
    new_text: str,
    *,
    repo_path: str | Path = ".",
) -> ToolResult:
    """Apply one exact text replacement to a file."""
    operation = {
        "path": str(path),
        "old_text": old_text,
        "new_text": new_text,
    }
    return apply_replacements([operation], repo_path=repo_path)


def apply_replacements(
    operations: list[dict[str, str]],
    *,
    repo_path: str | Path = ".",
) -> ToolResult:
    """Apply multiple exact text replacements after validating all of them."""
    if not operations:
        return fail("at least one replacement operation is required")

    repo = Path(repo_path).resolve()
    validation = _validate_replacements(operations, repo)
    if not validation["ok"]:
        return validation

    file_updates: dict[Path, dict[str, Any]] = validation["data"]["file_updates"]
    changed_files = []
    file_hashes: dict[str, dict[str, str]] = {}

    for file_path, update in file_updates.items():
        before_content = update["before_content"]
        after_content = update["after_content"]
        if before_content == after_content:
            continue

        file_path.write_text(after_content, encoding="utf-8")
        relative_path = _relative_display_path(file_path, repo)
        changed_files.append(relative_path)
        file_hashes[relative_path] = {
            "before_sha256": _sha256_text(before_content),
            "after_sha256": _sha256_text(after_content),
        }

    return ok(
        {
            "changed": bool(changed_files),
            "changed_files": changed_files,
            "operations": len(operations),
            "file_hashes": file_hashes,
        }
    )


def write_file(
    path: str | Path,
    content: str,
    *,
    repo_path: str | Path = ".",
    expected_old_content: str | None = None,
) -> ToolResult:
    """Overwrite one file with optional optimistic concurrency protection."""
    repo = Path(repo_path).resolve()
    path_result = _resolve_writable_path(path, repo)
    if not path_result["ok"]:
        return path_result

    file_path: Path = path_result["data"]["path"]
    before_content = ""
    if file_path.exists():
        if not file_path.is_file():
            return fail(f"path is not a file: {_relative_display_path(file_path, repo)}")
        before_content = file_path.read_text(encoding="utf-8")

    if expected_old_content is not None and before_content != expected_old_content:
        return fail(
            "current file content does not match expected_old_content",
            {
                "path": _relative_display_path(file_path, repo),
                "before_sha256": _sha256_text(before_content),
                "expected_sha256": _sha256_text(expected_old_content),
            },
        )

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    return ok(
        {
            "changed": before_content != content,
            "path": _relative_display_path(file_path, repo),
            "before_sha256": _sha256_text(before_content),
            "after_sha256": _sha256_text(content),
        }
    )


def _validate_replacements(
    operations: list[dict[str, str]],
    repo: Path,
) -> ToolResult:
    file_updates: dict[Path, dict[str, Any]] = {}

    for index, operation in enumerate(operations):
        path = operation.get("path")
        old_text = operation.get("old_text")
        new_text = operation.get("new_text")

        if not path:
            return fail(f"operation {index} is missing path")
        if old_text is None or old_text == "":
            return fail(f"operation {index} is missing old_text")
        if new_text is None:
            return fail(f"operation {index} is missing new_text")

        path_result = _resolve_writable_path(path, repo)
        if not path_result["ok"]:
            return fail(path_result["error"], {"failed_operation": operation, "applied": False})

        file_path: Path = path_result["data"]["path"]
        if not file_path.exists():
            return fail(
                f"file does not exist: {path}",
                {"failed_operation": operation, "applied": False},
            )

        current_content = file_updates.get(file_path, {}).get("after_content")
        if current_content is None:
            current_content = file_path.read_text(encoding="utf-8")
            file_updates[file_path] = {
                "before_content": current_content,
                "after_content": current_content,
            }

        occurrences = current_content.count(old_text)
        if occurrences == 0:
            return fail(
                f"old_text not found in {path}",
                {"failed_operation": operation, "applied": False},
            )
        if occurrences > 1:
            return fail(
                f"old_text is ambiguous in {path}: found {occurrences} occurrences",
                {"failed_operation": operation, "applied": False},
            )

        file_updates[file_path]["after_content"] = current_content.replace(
            old_text,
            new_text,
            1,
        )

    return ok({"file_updates": file_updates})


def _resolve_writable_path(path: str | Path, repo: Path) -> ToolResult:
    raw_path = Path(path)
    file_path = raw_path if raw_path.is_absolute() else repo / raw_path
    resolved = file_path.resolve()

    try:
        resolved.relative_to(repo)
    except ValueError:
        return fail(f"path is outside repo: {path}")

    relative_path = _relative_display_path(resolved, repo)
    parts = set(Path(relative_path).parts)
    if parts & BLOCKED_PATH_PARTS:
        return fail(f"path is blocked: {relative_path}")
    if resolved.name in BLOCKED_FILE_NAMES:
        return fail(f"file name is blocked: {relative_path}")
    if relative_path in BLOCKED_RELATIVE_PATHS:
        return fail(f"path is blocked: {relative_path}")

    return ok({"path": resolved, "relative_path": relative_path})


def _relative_display_path(path: Path, repo: Path) -> str:
    try:
        return str(path.relative_to(repo))
    except ValueError:
        return str(path)


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
