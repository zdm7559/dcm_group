from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


ToolResult = dict[str, Any]
DEFAULT_TEST_COMMAND = [sys.executable, "-m", "pytest", "tests/"]


def ok(data: Any = None) -> ToolResult:
    return {"ok": True, "data": data, "error": None}


def fail(error: str, data: Any = None) -> ToolResult:
    return {"ok": False, "data": data, "error": error}


def run_tests(
    command: list[str] | None = None,
    *,
    cwd: str | Path = ".",
    timeout: int = 120,
    summary_lines: int = 40,
) -> ToolResult:
    """Run the project test command and return structured test output."""
    test_command = command or DEFAULT_TEST_COMMAND

    try:
        result = subprocess.run(
            test_command,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _decode_timeout_output(exc.stdout)
        stderr = _decode_timeout_output(exc.stderr)
        data = {
            "passed": False,
            "exit_code": None,
            "command": test_command,
            "stdout": stdout,
            "stderr": stderr,
            "summary": tail_text(f"{stdout}\n{stderr}", summary_lines),
        }
        return fail(f"tests timed out after {timeout} seconds", data)

    combined_output = f"{result.stdout}\n{result.stderr}"
    data = {
        "passed": result.returncode == 0,
        "exit_code": result.returncode,
        "command": test_command,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "summary": tail_text(combined_output, summary_lines),
    }

    if result.returncode == 0:
        return ok(data)

    return fail("tests failed", data)


def tail_text(text: str, line_count: int) -> str:
    if line_count <= 0:
        return ""

    lines = text.splitlines()
    return "\n".join(lines[-line_count:])


def _decode_timeout_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output
