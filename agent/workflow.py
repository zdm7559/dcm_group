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
ProgressCallback = Callable[[str], None]


def ok(data: Any = None) -> ToolResult:
    return {"ok": True, "data": data, "error": None}


def fail(error: str, data: Any = None) -> ToolResult:
    return {"ok": False, "data": data, "error": error}


def run_once(
    *,
    repo_path: str = ".",
    max_attempts: int = 3,
    progress: ProgressCallback | None = None,
) -> ToolResult:
    log_result = _read_grouped_errors(repo_path=repo_path, progress=progress)
    if not log_result["ok"]:
        return log_result

    selected_error = _select_error(log_result["data"]["errors"])
    return _run_for_error(
        selected_error,
        repo_path=repo_path,
        max_attempts=max_attempts,
        progress=progress,
    )


def run_all(
    *,
    repo_path: str = ".",
    max_attempts: int = 3,
    progress: ProgressCallback | None = None,
) -> ToolResult:
    log_result = _read_grouped_errors(repo_path=repo_path, progress=progress)
    if not log_result["ok"]:
        return log_result

    error_groups = log_result["data"]["errors"]
    total = len(error_groups)
    _emit(progress, f"发现 {total} 类错误，开始批量修复")

    results = []
    for index, error_group in enumerate(error_groups, start=1):
        selected_error = error_group["latest"]
        _emit(
            progress,
            (
                f"批量进度 {index}/{total}："
                f"{selected_error.get('exception_type')} "
                f"{selected_error.get('path')} "
                f"occurrences={error_group.get('occurrences')}"
            ),
        )
        result = _run_for_error(
            selected_error,
            repo_path=repo_path,
            max_attempts=max_attempts,
            progress=progress,
        )
        results.append(
            {
                "fingerprint": error_group.get("fingerprint"),
                "occurrences": error_group.get("occurrences"),
                "result": result,
            }
        )

        if result["ok"]:
            _emit(progress, f"批量进度 {index}/{total} 完成")
        else:
            _emit(progress, f"批量进度 {index}/{total} 失败：{result['error']}")

    succeeded = sum(1 for item in results if item["result"]["ok"])
    failed = total - succeeded
    if failed == 0:
        _emit(progress, f"批量修复完成：{succeeded}/{total} 成功")
        return ok({"total": total, "succeeded": succeeded, "failed": failed, "results": results})

    _emit(progress, f"批量修复结束：{succeeded}/{total} 成功，{failed} 个失败")
    return fail(
        f"batch completed with {failed} failed error groups",
        {"total": total, "succeeded": succeeded, "failed": failed, "results": results},
    )


def _read_grouped_errors(*, repo_path: str, progress: ProgressCallback | None) -> ToolResult:
    repo = Path(repo_path)
    error_log_path = repo / "logs" / "error.log"
    _emit(progress, "读取错误日志 logs/error.log")
    log_result = read_error_logs(log_path=error_log_path, mode="grouped")
    if not log_result["ok"]:
        _emit(progress, f"读取错误日志失败：{log_result['error']}")
    return log_result


def _run_for_error(
    selected_error: dict[str, Any],
    *,
    repo_path: str,
    max_attempts: int,
    progress: ProgressCallback | None,
) -> ToolResult:
    _emit(
        progress,
        (
            "选中错误："
            f"{selected_error.get('exception_type')} "
            f"{selected_error.get('path')} "
            f"fingerprint={selected_error.get('fingerprint')}"
        ),
    )

    context_hints = selected_error.get("context_hints", {})
    files_to_read = context_hints.get("files_to_read", [])
    if files_to_read:
        _emit(progress, f"读取相关源码：{', '.join(files_to_read)}")
    else:
        _emit(progress, "读取相关源码")

    context_result = read_files_for_error(selected_error, repo_path=repo_path)
    if not context_result["ok"]:
        _emit(progress, f"读取源码失败：{context_result['error']}")
        return context_result

    code_context = context_result["data"]["files"]
    _emit(progress, f"已读取 {len(code_context)} 个源码上下文，开始让 LLM 诊断")
    diagnosis_result = _diagnose(selected_error, code_context)
    if not diagnosis_result["ok"]:
        _emit(progress, f"LLM 诊断失败：{diagnosis_result['error']}")
        return diagnosis_result

    diagnosis = diagnosis_result["data"]
    _emit(progress, f"诊断完成：{diagnosis.get('root_cause', '未提供 root_cause')}")
    files_to_modify = diagnosis.get("files_to_modify", [])
    if files_to_modify:
        _emit(progress, f"计划修改文件：{', '.join(files_to_modify)}")

    previous_failure = None
    last_write_result = None
    last_test_result = None

    for attempt in range(1, max_attempts + 1):
        _emit(progress, f"第 {attempt}/{max_attempts} 次尝试：生成修复操作")
        fix_result = _generate_fix_operations(
            selected_error,
            code_context,
            diagnosis,
            previous_failure=previous_failure,
        )
        if not fix_result["ok"]:
            _emit(progress, f"生成修复操作失败：{fix_result['error']}")
            return fix_result

        operations = fix_result["data"].get("operations", [])
        _emit(progress, f"生成 {len(operations)} 个替换操作，开始写入文件")
        write_result = apply_replacements(operations, repo_path=repo_path)
        last_write_result = write_result
        if not write_result["ok"]:
            _emit(progress, f"写入失败：{write_result['error']}，准备重试")
            previous_failure = {
                "attempt": attempt,
                "stage": "write",
                "error": write_result["error"],
                "data": write_result["data"],
            }
            continue

        changed_files = write_result.get("data", {}).get("changed_files", [])
        if changed_files:
            _emit(progress, f"已修改文件：{', '.join(changed_files)}")
        else:
            _emit(progress, "替换操作执行完成，但文件内容没有变化")

        _emit(progress, "检查已修改 Python 文件语法")
        syntax_result = _check_changed_python_files(write_result, repo_path=repo_path)
        if not syntax_result["ok"]:
            _emit(progress, f"语法检查失败：{syntax_result['error']}，回滚本次修改")
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
        _emit(progress, f"语法检查通过，运行定向测试：{' '.join(test_command)}")
        test_result = run_tests(command=test_command, cwd=repo_path)
        last_test_result = test_result
        if test_result["ok"]:
            _emit(progress, "定向测试通过，保存修复记录")
            record_result = save_fix_record(
                error_event=selected_error,
                diagnosis=diagnosis,
                write_result=write_result,
                test_result=test_result,
                repo_path=repo_path,
            )
            record_path = record_result.get("data", {}).get("path") if record_result.get("ok") else None
            if record_path:
                _emit(progress, f"修复记录已保存：{record_path}")
            _emit(progress, "本次 AutoFix 成功完成")
            return ok(
                {
                    "error": selected_error,
                    "diagnosis": diagnosis,
                    "write_result": write_result,
                    "test_result": test_result,
                    "record": record_result,
                }
            )

        _emit(progress, f"定向测试失败：{test_result['error']}，回滚本次修改后重试")
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
    _emit(progress, f"{max_attempts} 次尝试后仍未通过测试，已保存失败记录")
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


def _emit(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)


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
    elif path == "/validation/missing-required":
        return [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_service.py::test_missing_required_param_should_return_400",
        ]
    elif path == "/validation/bad-age":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_bad_age_param_should_return_400"]
    elif path == "/validation/bad-range":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_bad_range_param_should_return_400"]
    elif path == "/validation/empty-username":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_empty_username_should_return_400"]
    elif path == "/nulls/missing-user":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_missing_user_null_should_return_404"]
    elif path == "/nulls/none-email":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_none_email_should_return_400"]
    elif path == "/body/missing-age":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_missing_body_age_should_return_400"]
    elif path == "/conversion/int-string":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_int_string_should_return_400"]
    elif path == "/conversion/float-string":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_float_string_should_return_400"]
    elif path == "/conversion/bad-date":
        return [sys.executable, "-m", "pytest", "tests/test_service.py::test_bad_date_should_return_400"]
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
