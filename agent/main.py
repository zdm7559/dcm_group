from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from agent.workflow import run_once


def main() -> None:
    parser = argparse.ArgumentParser(description="运行一次 AutoFix Agent。")
    parser.add_argument("--repo-path", default=".", help="项目根目录。")
    parser.add_argument("--max-attempts", type=int, default=3, help="最大修复尝试次数。")
    parser.add_argument("--json", action="store_true", help="输出完整结构化 JSON 结果。")
    args = parser.parse_args()

    progress = None if args.json else print_progress
    result = run_once(repo_path=args.repo_path, max_attempts=args.max_attempts, progress=progress)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_summary(result)

    if not result["ok"]:
        sys.exit(1)


def print_progress(event: str, payload: dict[str, Any]) -> None:
    message = format_progress(event, payload)
    if message:
        print(message, flush=True)


def format_progress(event: str, payload: dict[str, Any]) -> str | None:
    if event == "start":
        return (
            f"[开始] AutoFix Agent 项目目录={payload['repo_path']} "
            f"最大尝试次数={payload['max_attempts']}"
        )
    if event == "read_log":
        return "[1/8] 正在读取错误日志..."
    if event == "read_log_done":
        return f"[1/8] 已发现 {payload['groups']} 组错误。"
    if event == "select_error":
        return (
            "[2/8] 已选择待修复错误："
            f"{payload.get('exception_type')}，接口 {payload.get('path')} "
            f"(fingerprint={payload.get('fingerprint')})"
        )
    if event == "read_files":
        return "[3/8] 正在读取相关源码文件..."
    if event == "read_files_done":
        return f"[3/8] 已读取文件：{_join_values(payload.get('files', []))}"
    if event == "diagnose":
        return "[4/8] 正在调用大模型分析错误根因..."
    if event == "diagnose_done":
        return (
            "[4/8] 根因分析完成："
            f"风险等级={payload.get('risk_level')}，"
            f"建议修改文件={_join_values(payload.get('files_to_modify', []))}"
        )
    if event == "attempt_start":
        return f"[第 {payload['attempt']}/{payload['max_attempts']} 次尝试] 开始生成并验证修复。"
    if event == "generate_patch":
        return "[5/8] 正在调用大模型生成代码修改操作..."
    if event == "generate_patch_done":
        return f"[5/8] 已生成 {payload['operations']} 个修改操作。"
    if event == "write_files":
        return "[6/8] 正在写入代码修改..."
    if event == "write_done":
        return f"[6/8] 已修改文件：{_join_values(payload.get('changed_files', []))}"
    if event == "write_failed":
        return f"[6/8] 写入失败：{payload.get('error')}"
    if event == "syntax_check":
        return "[7/8] 正在检查 Python 语法..."
    if event == "syntax_done":
        checked_files = payload.get("checked_files", [])
        if not checked_files:
            return "[7/8] 没有修改 Python 文件，跳过语法检查。"
        return f"[7/8] 语法检查通过：{_join_values(checked_files)}"
    if event == "syntax_failed":
        return f"[7/8] 语法检查失败：{payload.get('error')}"
    if event == "run_tests":
        return f"[8/8] 正在运行目标测试：{' '.join(payload.get('command', []))}"
    if event == "tests_done":
        return "[8/8] 目标测试通过。"
    if event == "tests_failed":
        return f"[8/8] 目标测试失败：{payload.get('error')}"
    if event == "restore_done":
        return f"[回滚] 已恢复文件：{_join_values(payload.get('restored_files', []))}"
    if event == "save_record":
        return "[记录] 正在保存修复记录..."
    if event == "done":
        return f"[完成] 修复成功。记录文件：{payload.get('record')}"
    if event == "failed":
        return f"[失败] 阶段={payload.get('stage')}，原因={payload.get('error')}"
    return None


def print_summary(result: dict[str, Any]) -> None:
    print("")
    if result["ok"]:
        data = result["data"]
        error_event = data["error"]
        write_data = data["write_result"]["data"]
        test_data = data["test_result"]["data"]
        record_data = data["record"]["data"] if data["record"]["ok"] else {}

        print("结果：成功")
        print(f"已修复错误：{error_event.get('exception_type')}，接口 {error_event.get('path')}")
        print(f"修改文件：{_join_values(write_data.get('changed_files', []))}")
        print(f"测试命令：{' '.join(test_data.get('command', []))}")
        print(f"修复记录：{record_data.get('path')}")
        return

    print("结果：失败")
    print(f"错误原因：{result['error']}")


def _join_values(values: list[Any]) -> str:
    if not values:
        return "无"
    return ", ".join(str(value) for value in values)


if __name__ == "__main__":
    main()
