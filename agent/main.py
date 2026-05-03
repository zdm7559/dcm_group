from __future__ import annotations

import argparse
import json
from datetime import datetime

from agent.workflow import run_all, run_once


def print_progress(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def print_summary(result: dict) -> None:
    print()
    print("=== AutoFix Summary ===")
    print(f"status: {'success' if result.get('ok') else 'failed'}")
    if result.get("error"):
        print(f"error: {result['error']}")

    data = result.get("data") or {}
    if "results" in data:
        print(f"total: {data.get('total')}")
        print(f"succeeded: {data.get('succeeded')}")
        print(f"failed: {data.get('failed')}")
        for index, item in enumerate(data.get("results", []), start=1):
            item_result = item.get("result", {})
            item_data = item_result.get("data") or {}
            error_event = item_data.get("error") or item_data.get("last_error") or {}
            path = error_event.get("path", "unknown")
            exception_type = error_event.get("exception_type", "unknown")
            status = "success" if item_result.get("ok") else "failed"
            print(f"{index}. {status}: {exception_type} {path}")
        return

    error_event = data.get("error") or data.get("last_error") or {}
    if error_event:
        print(f"bug: {error_event.get('exception_type')} {error_event.get('path')}")
        print(f"fingerprint: {error_event.get('fingerprint')}")

    diagnosis = data.get("diagnosis") or {}
    if diagnosis.get("root_cause"):
        print(f"root_cause: {diagnosis['root_cause']}")

    write_result = data.get("write_result") or data.get("last_write_result") or {}
    changed_files = write_result.get("data", {}).get("changed_files", [])
    if changed_files:
        print(f"changed_files: {', '.join(changed_files)}")

    test_result = data.get("test_result") or data.get("last_test_result") or {}
    test_data = test_result.get("data") or {}
    if test_data:
        print(f"test_passed: {test_data.get('passed')}")
        print(f"test_exit_code: {test_data.get('exit_code')}")

    record = data.get("record") or {}
    record_path = record.get("data", {}).get("path")
    if record_path:
        print(f"record: {record_path}")

    post_actions = data.get("post_actions") or {}
    branch_name = post_actions.get("branch_name")
    if branch_name:
        print(f"branch: {branch_name}")

    pr_result = post_actions.get("pr_result") or {}
    pr_data = pr_result.get("data") or {}
    if pr_data.get("url"):
        print(f"pr: {pr_data['url']}")
    elif pr_result.get("error"):
        print(f"pr_error: {pr_result['error']}")

    feishu_result = post_actions.get("feishu_result") or {}
    if feishu_result.get("ok") is True:
        print("feishu: sent")
    elif feishu_result.get("error"):
        print(f"feishu_error: {feishu_result['error']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AutoFix Agent once.")
    parser.add_argument("--repo-path", default=".", help="Repository root path.")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum repair attempts.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full structured JSON result instead of human-readable progress.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Repair every grouped error found in logs/error.log instead of only the selected error.",
    )
    args = parser.parse_args()

    if args.json:
        runner = run_all if args.all else run_once
        result = runner(repo_path=args.repo_path, max_attempts=args.max_attempts)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print_progress("启动 AutoFix Agent")
    runner = run_all if args.all else run_once
    result = runner(
        repo_path=args.repo_path,
        max_attempts=args.max_attempts,
        progress=print_progress,
    )
    print_summary(result)


if __name__ == "__main__":
    main()
