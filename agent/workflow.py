from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from agent.fix_records import save_fix_record
from agent.llm_client import call_llm
from agent.prompts import build_diagnosis_messages, build_fix_messages
from agent.tools import apply_replacements, read_error_logs, read_files_for_error, restore_files, run_tests


ToolResult = dict[str, Any]
ProgressReporter = Callable[[str, dict[str, Any]], None]


def ok(data: Any = None) -> ToolResult:
    return {"ok": True, "data": data, "error": None}


def fail(error: str, data: Any = None) -> ToolResult:
    return {"ok": False, "data": data, "error": error}


def run_once(
    *,
    repo_path: str = ".",
    max_attempts: int = 3,
    progress: ProgressReporter | None = None,
) -> ToolResult:
    _report(progress, "start", repo_path=repo_path, max_attempts=max_attempts)

    _report(progress, "read_log")
    log_result = read_error_logs(mode="grouped")
    if not log_result["ok"]:
        _report(progress, "failed", stage="read_log", error=log_result["error"])
        return log_result
    _report(progress, "read_log_done", groups=log_result["data"]["count"])

    selected_error = _select_error(log_result["data"]["errors"])
    _report(
        progress,
        "select_error",
        path=selected_error.get("path"),
        exception_type=selected_error.get("exception_type"),
        fingerprint=selected_error.get("fingerprint"),
    )

    _report(progress, "read_files")
    context_result = read_files_for_error(selected_error, repo_path=repo_path)
    if not context_result["ok"]:
        _report(progress, "failed", stage="read_files", error=context_result["error"])
        return context_result

    code_context = context_result["data"]["files"]
    _report(
        progress,
        "read_files_done",
        files=[item.get("path") for item in code_context],
    )

    _report(progress, "diagnose")
    diagnosis_result = _diagnose(selected_error, code_context)
    if not diagnosis_result["ok"]:
        _report(progress, "failed", stage="diagnose", error=diagnosis_result["error"])
        return diagnosis_result

    diagnosis = diagnosis_result["data"]
    _report(
        progress,
        "diagnose_done",
        risk_level=diagnosis.get("risk_level"),
        files_to_modify=diagnosis.get("files_to_modify", []),
    )
    previous_failure = None
    last_write_result = None
    last_test_result = None

    for attempt in range(1, max_attempts + 1):
        _report(progress, "attempt_start", attempt=attempt, max_attempts=max_attempts)
        _report(progress, "generate_patch", attempt=attempt)
        fix_result = _generate_fix_operations(
            selected_error,
            code_context,
            diagnosis,
            previous_failure=previous_failure,
        )
        if not fix_result["ok"]:
            _report(progress, "failed", stage="generate_patch", error=fix_result["error"])
            return fix_result

        operations = fix_result["data"].get("operations", [])
        _report(progress, "generate_patch_done", attempt=attempt, operations=len(operations))
        _report(progress, "write_files", attempt=attempt, operations=len(operations))
        write_result = apply_replacements(operations, repo_path=repo_path)
        last_write_result = write_result
        if not write_result["ok"]:
            _report(progress, "write_failed", attempt=attempt, error=write_result["error"])
            previous_failure = {
                "attempt": attempt,
                "stage": "write",
                "error": write_result["error"],
                "data": write_result["data"],
            }
            continue
        _report(
            progress,
            "write_done",
            attempt=attempt,
            changed_files=write_result.get("data", {}).get("changed_files", []),
        )

        _report(progress, "syntax_check", attempt=attempt)
        syntax_result = _check_changed_python_files(write_result, repo_path=repo_path)
        if not syntax_result["ok"]:
            _report(progress, "syntax_failed", attempt=attempt, error=syntax_result["error"])
            restore_result = _restore_write_result(write_result, repo_path=repo_path)
            _report(
                progress,
                "restore_done",
                attempt=attempt,
                restored_files=restore_result.get("data", {}).get("restored_files", []),
            )
            previous_failure = {
                "attempt": attempt,
                "stage": "syntax",
                "error": syntax_result["error"],
                "summary": syntax_result["data"].get("summary") if syntax_result.get("data") else None,
                "restore_result": restore_result,
            }
            continue
        _report(
            progress,
            "syntax_done",
            attempt=attempt,
            checked_files=syntax_result.get("data", {}).get("checked_files", []),
        )

        test_command = _target_test_command(selected_error)
        _report(progress, "run_tests", attempt=attempt, command=test_command)
        test_result = run_tests(command=test_command, cwd=repo_path)
        last_test_result = test_result
        if test_result["ok"]:
            _report(progress, "tests_done", attempt=attempt, passed=True)
            _report(progress, "save_record")
            record_result = save_fix_record(
                error_event=selected_error,
                diagnosis=diagnosis,
                write_result=write_result,
                test_result=test_result,
                repo_path=repo_path,
            )
            _report(
                progress,
                "done",
                record=record_result.get("data", {}).get("path"),
                changed_files=write_result.get("data", {}).get("changed_files", []),
            )
            return ok(
                {
                    "error": selected_error,
                    "diagnosis": diagnosis,
                    "write_result": write_result,
                    "test_result": test_result,
                    "record": record_result,
                }
            )

        _report(progress, "tests_failed", attempt=attempt, error=test_result["error"])
        restore_result = _restore_write_result(write_result, repo_path=repo_path)
        _report(
            progress,
            "restore_done",
            attempt=attempt,
            restored_files=restore_result.get("data", {}).get("restored_files", []),
        )
        previous_failure = {
            "attempt": attempt,
            "stage": "test",
            "error": test_result["error"],
            "summary": test_result["data"].get("summary") if test_result.get("data") else None,
            "restore_result": restore_result,
        }

    record_result = save_fix_record(
        error_event=selected_error,
        diagnosis=diagnosis,
        write_result=last_write_result,
        test_result=last_test_result,
        repo_path=repo_path,
    )
    _report(progress, "failed", stage="workflow", error=f"failed after {max_attempts} attempts")
    return fail(
        f"failed to produce passing tests after {max_attempts} attempts",
        {
            "error": selected_error,
            "diagnosis": diagnosis,
            "last_write_result": last_write_result,
            "last_test_result": last_test_result,
            "record": record_result,
        },
    )


def _report(progress: ProgressReporter | None, event: str, **payload: Any) -> None:
    if progress is None:
        return
    progress(event, payload)


def _select_error(error_groups: list[dict[str, Any]]) -> dict[str, Any]:
    return error_groups[0]["latest"]


def _check_changed_python_files(write_result: ToolResult, *, repo_path: str) -> ToolResult:
    changed_files = write_result.get("data", {}).get("changed_files", [])
    python_files = [path for path in changed_files if str(path).endswith(".py")]
    if not python_files:
        return ok({"checked_files": []})

    command = [sys.executable, "-m", "py_compile", *python_files]
    result = subprocess.run(
        command,
        cwd=str(Path(repo_path)),
        text=True,
        capture_output=True,
        check=False,
    )
    data = {
        "checked_files": python_files,
        "command": command,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "summary": "\n".join(f"{result.stdout}\n{result.stderr}".splitlines()[-20:]),
    }
    if result.returncode == 0:
        return ok(data)

    return fail("syntax check failed", data)


def _restore_write_result(write_result: ToolResult, *, repo_path: str) -> ToolResult:
    before_contents = write_result.get("data", {}).get("before_contents", {})
    return restore_files(before_contents, repo_path=repo_path)


def _target_test_command(error_event: dict[str, Any]) -> list[str]:
    path = error_event.get("path")
    exception_type = error_event.get("exception_type")

    if path == "/divide" or exception_type == "ZeroDivisionError":
        return [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_service.py::test_divide_by_zero_should_return_400",
        ]

    if str(path).startswith("/users/") or exception_type == "KeyError":
        return [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_service.py::test_user_not_found_should_return_404",
        ]

    return [sys.executable, "-m", "pytest", "tests/"]


def _diagnose(error_event: dict[str, Any], code_context: list[dict[str, Any]]) -> ToolResult:
    llm_result = call_llm(build_diagnosis_messages(error_event=error_event, code_context=code_context))
    if not llm_result["ok"]:
        return llm_result

    return _parse_llm_json(llm_result["data"]["content"])


def _generate_fix_operations(
    error_event: dict[str, Any],
    code_context: list[dict[str, Any]],
    diagnosis: dict[str, Any],
    *,
    previous_failure: dict[str, Any] | None = None,
) -> ToolResult:
    llm_result = call_llm(
        build_fix_messages(
            error_event=error_event,
            code_context=code_context,
            diagnosis=diagnosis,
            previous_failure=previous_failure,
        )
    )
    if not llm_result["ok"]:
        return llm_result

    parsed_result = _parse_llm_json(llm_result["data"]["content"])
    if not parsed_result["ok"]:
        return parsed_result

    operations = parsed_result["data"].get("operations")
    if not isinstance(operations, list) or not operations:
        return fail("LLM fix response must contain a non-empty operations list", parsed_result["data"])

    return parsed_result


def _parse_llm_json(content: str) -> ToolResult:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return fail(f"LLM did not return valid JSON: {exc}", {"content": content})

    if not isinstance(parsed, dict):
        return fail("LLM JSON response must be an object", {"content": content})

    return ok(parsed)
