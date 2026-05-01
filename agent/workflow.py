from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent.fix_records import save_fix_record
from agent.llm_client import call_llm
from agent.prompts import build_diagnosis_messages, build_fix_messages
from agent.tools import apply_replacements, read_error_logs, read_files_for_error, restore_files, run_tests


ToolResult = dict[str, Any]


def ok(data: Any = None) -> ToolResult:
    return {"ok": True, "data": data, "error": None}


def fail(error: str, data: Any = None) -> ToolResult:
    return {"ok": False, "data": data, "error": error}


def run_once(
    *,
    repo_path: str = ".",
    max_attempts: int = 3,
) -> ToolResult:
    log_result = read_error_logs(mode="grouped")
    if not log_result["ok"]:
        return log_result

    selected_error = _select_error(log_result["data"]["errors"])
    context_result = read_files_for_error(selected_error, repo_path=repo_path)
    if not context_result["ok"]:
        return context_result

    code_context = context_result["data"]["files"]
    diagnosis_result = _diagnose(selected_error, code_context)
    if not diagnosis_result["ok"]:
        return diagnosis_result

    diagnosis = diagnosis_result["data"]
    previous_failure = None
    last_write_result = None
    last_test_result = None

    for attempt in range(1, max_attempts + 1):
        fix_result = _generate_fix_operations(
            selected_error,
            code_context,
            diagnosis,
            previous_failure=previous_failure,
        )
        if not fix_result["ok"]:
            return fix_result

        operations = fix_result["data"].get("operations", [])
        write_result = apply_replacements(operations, repo_path=repo_path)
        last_write_result = write_result
        if not write_result["ok"]:
            previous_failure = {
                "attempt": attempt,
                "stage": "write",
                "error": write_result["error"],
                "data": write_result["data"],
            }
            continue

        syntax_result = _check_changed_python_files(write_result, repo_path=repo_path)
        if not syntax_result["ok"]:
            restore_result = _restore_write_result(write_result, repo_path=repo_path)
            previous_failure = {
                "attempt": attempt,
                "stage": "syntax",
                "error": syntax_result["error"],
                "summary": syntax_result["data"].get("summary") if syntax_result.get("data") else None,
                "restore_result": restore_result,
            }
            continue

        test_command = _target_test_command(selected_error)
        test_result = run_tests(command=test_command, cwd=repo_path)
        last_test_result = test_result
        if test_result["ok"]:
            record_result = save_fix_record(
                error_event=selected_error,
                diagnosis=diagnosis,
                write_result=write_result,
                test_result=test_result,
                repo_path=repo_path,
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

        restore_result = _restore_write_result(write_result, repo_path=repo_path)
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
    if path == "/request/invalid-json":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_invalid_json_should_return_400"]
    elif path == "/files/missing-config":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_missing_config_should_not_return_500"]
    elif path == "/files/missing-log-dir":
        return [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_service.py::test_missing_log_dir_should_create_directory",
        ]
    elif path == "/config/missing-api-key":
        return [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_service.py::test_missing_api_key_should_return_client_or_service_error",
        ]
    elif path == "/config/invalid-timeout":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_invalid_timeout_should_return_400"]
    elif path == "/dependencies/missing-yaml":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_missing_yaml_should_not_return_500"]
    elif path == "/dependencies/bad-import":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_bad_import_should_not_return_500"]
    elif path == "/naming/unknown-function":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_unknown_function_should_return_200"]
    elif path == "/data/missing-profile":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_missing_profile_should_return_404"]
    elif path == "/resources/not-found-as-500":
        return [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_service.py::test_not_found_resource_should_return_404",
        ]
    elif path == "/divide" or (path is None and exception_type == "ZeroDivisionError"):
        return [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_service.py::test_divide_by_zero_should_return_400",
        ]
    elif str(path).startswith("/users/") or (path is None and exception_type == "KeyError"):
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
