from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """你是 AutoFix Agent 的代码修复模型。
你只负责诊断和生成结构化替换操作，不负责执行命令。
必须优先做最小修改，保持现有项目风格，并让测试通过。
输出必须是合法 JSON，不要输出 Markdown。"""


def build_diagnosis_messages(
    *,
    error_event: dict[str, Any],
    code_context: list[dict[str, Any]],
) -> list[dict[str, str]]:
    payload = {
        "error_event": _compact_error_event(error_event),
        "code_context": _compact_code_context(code_context),
        "task": "分析根因，说明应该修改哪些文件和修复策略。只输出 JSON。",
        "expected_schema": {
            "root_cause": "string",
            "fix_strategy": "string",
            "files_to_modify": ["path"],
            "risk_level": "low|medium|high",
        },
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def build_fix_messages(
    *,
    error_event: dict[str, Any],
    code_context: list[dict[str, Any]],
    diagnosis: dict[str, Any],
    previous_failure: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    payload = {
        "error_event": _compact_error_event(error_event),
        "code_context": _compact_code_context(code_context),
        "diagnosis": diagnosis,
        "previous_failure": previous_failure,
        "task": (
            "生成可由 apply_replacements 执行的精确替换操作。old_text 必须来自源码原文，且应唯一匹配。"
            "new_text 必须是完整、语法合法、缩进正确的代码片段；不要生成重复嵌套的 try/except；"
            "如果 previous_failure 里出现语法错误，必须基于原始 code_context 重新生成完整替换块。"
        ),
        "expected_schema": {
            "operations": [
                {
                    "path": "relative/path.py",
                    "old_text": "exact source text to replace",
                    "new_text": "new source text",
                }
            ],
            "explanation": "string",
        },
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def _compact_error_event(error_event: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": error_event.get("timestamp"),
        "path": error_event.get("path"),
        "path_params": error_event.get("path_params"),
        "query": error_event.get("query"),
        "exception_type": error_event.get("exception_type"),
        "exception_message": error_event.get("exception_message"),
        "traceback": error_event.get("traceback"),
        "project_frames": error_event.get("project_frames"),
        "suspect_frame": error_event.get("suspect_frame"),
        "context_hints": error_event.get("context_hints"),
        "fingerprint": error_event.get("fingerprint"),
    }


def _compact_code_context(code_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "path": item.get("path"),
            "read_mode": item.get("read_mode"),
            "symbol": item.get("symbol"),
            "line_start": item.get("line_start"),
            "line_end": item.get("line_end"),
            "content": item.get("content"),
        }
        for item in code_context
    ]
