from __future__ import annotations

import json
from pathlib import Path
from typing import Any



DEFAULT_MAX_CHARS = 8000
DEFAULT_ALLOWED_ROOTS = [
    Path.cwd(),
    Path.cwd() / "logs",
    Path.cwd() / "agent",
]


def _resolve_allowed_roots(allowed_roots: list[str] | None = None) -> list[Path]:
    roots = allowed_roots or [str(path) for path in DEFAULT_ALLOWED_ROOTS]
    return [Path(root).expanduser().resolve() for root in roots]


def _is_path_allowed(target_path: Path, allowed_roots: list[Path]) -> bool:
    for root in allowed_roots:
        try:
            target_path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _build_error(file_path: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "file_path": file_path,
        "content": "",
        "encoding": None,
        "line_range": None,
        "truncated": False,
        "message": message,
    }


def read_file_content(
    file_path: str,
    encoding: str = "utf-8",
    max_chars: int = DEFAULT_MAX_CHARS,
    start_line: int | None = None,
    end_line: int | None = None,
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    if not file_path or not file_path.strip():
        return _build_error(file_path, "file_path 不能为空")

    if max_chars <= 0:
        return _build_error(file_path, "max_chars 必须大于 0")

    if start_line is not None and start_line <= 0:
        return _build_error(file_path, "start_line 必须从 1 开始")

    if end_line is not None and end_line <= 0:
        return _build_error(file_path, "end_line 必须从 1 开始")

    if start_line is not None and end_line is not None and start_line > end_line:
        return _build_error(file_path, "start_line 不能大于 end_line")

    try:
        target_path = Path(file_path).expanduser().resolve(strict=False)
    except OSError as exc:
        return _build_error(file_path, f"路径解析失败: {exc}")

    safe_roots = _resolve_allowed_roots(allowed_roots)
    if not _is_path_allowed(target_path, safe_roots):
        allowed = ", ".join(str(root) for root in safe_roots)
        return _build_error(file_path, f"禁止读取该路径。允许目录: {allowed}")

    if not target_path.exists():
        return _build_error(file_path, "文件不存在")

    if not target_path.is_file():
        return _build_error(file_path, "目标路径不是普通文件")

    try:
        raw_bytes = target_path.read_bytes()
    except OSError as exc:
        return _build_error(file_path, f"读取文件失败: {exc}")

    if b"\x00" in raw_bytes[:1024]:
        return _build_error(file_path, "检测到疑似二进制文件，当前工具仅支持文本文件")

    try:
        text = raw_bytes.decode(encoding)
        used_encoding = encoding
    except UnicodeDecodeError:
        text = None
        used_encoding = None
        for candidate in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
            try:
                text = raw_bytes.decode(candidate)
                used_encoding = candidate
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            return _build_error(file_path, "文件解码失败，请尝试指定正确编码")

    if start_line is not None or end_line is not None:
        lines = text.splitlines()
        start_index = (start_line or 1) - 1
        end_index = end_line if end_line is not None else len(lines)
        text = "\n".join(lines[start_index:end_index])
        line_range = {
            "start_line": start_line or 1,
            "end_line": min(end_index, len(lines)),
        }
    else:
        line_range = None

    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]

    return {
        "success": True,
        "file_path": str(target_path),
        "content": text,
        "encoding": used_encoding,
        "line_range": line_range,
        "truncated": truncated,
        "message": "ok",
    }


def read_file(
    file_path: str,
    encoding: str = "utf-8",
    max_chars: int = DEFAULT_MAX_CHARS,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    result = read_file_content(
        file_path=file_path,
        encoding=encoding,
        max_chars=max_chars,
        start_line=start_line,
        end_line=end_line,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


