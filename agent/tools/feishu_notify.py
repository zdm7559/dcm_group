from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


ToolResult = dict[str, Any]
ENV_LOADED = False


def ok(data: Any = None) -> ToolResult:
    return {"ok": True, "data": data, "error": None}


def fail(error: str, data: Any = None) -> ToolResult:
    return {"ok": False, "data": data, "error": error}


def send_feishu_card(
    payload: dict[str, Any],
    *,
    webhook_url: str | None = None,
) -> ToolResult:
    """Send a Feishu webhook payload."""
    load_local_env()

    url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL")

    if not url:
        return fail("FEISHU_WEBHOOK_URL is not configured")

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return fail(f"Feishu webhook error {exc.code}: {error_body}")
    except urllib.error.URLError as exc:
        return fail(f"Feishu webhook request failed: {exc.reason}")

    try:
        response_data: Any = json.loads(response_text)
    except json.JSONDecodeError:
        response_data = response_text

    error_message = _extract_feishu_error(response_data)
    if error_message:
        return fail(error_message, response_data)

    return ok({"mode": "feishu", "response": response_data})


def build_review_card(
    *,
    title: str,
    bug_type: str,
    endpoint: str,
    branch: str,
    pr_url: str,
    test_result: str,
    risk_level: str = "low",
) -> dict[str, Any]:
    """Build a Feishu Card JSON 2.0 payload for the review notification."""
    status_label = "通过" if test_result == "passed" else "未通过"
    status_icon = "✅" if test_result == "passed" else "❌"
    risk_label = _risk_label(risk_level)
    template = "green" if test_result == "passed" else "red"

    return {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "config": {
                "wide_screen_mode": True,
            },
            "header": {
                "template": template,
                "title": {
                    "tag": "plain_text",
                    "content": title,
                },
            },
            "body": {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": (
                            f"{status_icon} **Agent 已完成自动修复流程**\n"
                            "请开发者 Review 本次修复内容，并确认是否可以合并。"
                        ),
                    },
                    {
                        "tag": "hr",
                    },
                    {
                        "tag": "markdown",
                        "content": (
                            f"**错误类型：** `{bug_type}`\n"
                            f"**错误接口：** `{endpoint}`\n"
                            f"**修复分支：** `{branch}`\n"
                            f"**测试结果：** {status_icon} {status_label}\n"
                            f"**风险等级：** {risk_label}"
                        ),
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "查看 PR",
                        },
                        "type": "primary",
                        "width": "fill",
                        "behaviors": [
                            {
                                "type": "open_url",
                                "default_url": pr_url,
                            }
                        ],
                    },
                ],
            },
        },
    }


def _risk_label(risk_level: str) -> str:
    labels = {
        "low": "低",
        "medium": "中",
        "high": "高",
    }
    return labels.get(risk_level.lower(), risk_level)


def _extract_feishu_error(response_data: Any) -> str | None:
    if not isinstance(response_data, dict):
        return None

    if "code" in response_data and response_data.get("code") != 0:
        return f"Feishu API error {response_data.get('code')}: {response_data.get('msg')}"

    if "StatusCode" in response_data and response_data.get("StatusCode") != 0:
        return (
            f"Feishu API error {response_data.get('StatusCode')}: "
            f"{response_data.get('StatusMessage')}"
        )

    return None


def load_local_env(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from a local .env file if it exists."""
    global ENV_LOADED
    if ENV_LOADED:
        return

    ENV_LOADED = True

    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value
