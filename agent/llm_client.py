from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


ToolResult = dict[str, Any]
DEFAULT_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_MODEL = "kimi-k2.6"


def ok(data: Any = None) -> ToolResult:
    return {"ok": True, "data": data, "error": None}


def fail(error: str, data: Any = None) -> ToolResult:
    return {"ok": False, "data": data, "error": error}


def call_llm(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float | None = None,
    timeout: int = 120,
) -> ToolResult:
    """Call an OpenAI-compatible chat completions API."""
    load_local_env()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fail("OPENAI_API_KEY is not configured")

    base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model_name = model or os.getenv("MODEL_NAME", DEFAULT_MODEL)
    request_body: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
    }
    configured_temperature = _resolve_temperature(temperature)
    if configured_temperature is not None:
        request_body["temperature"] = configured_temperature

    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return fail(f"LLM API error {exc.code}: {error_body}")
    except urllib.error.URLError as exc:
        return fail(f"LLM API request failed: {exc.reason}")
    except json.JSONDecodeError as exc:
        return fail(f"LLM API returned invalid JSON: {exc}")

    try:
        content = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        return fail(f"LLM API response missing message content: {exc}", response_data)

    return ok(
        {
            "content": content,
            "model": model_name,
            "temperature": configured_temperature,
            "raw_response": response_data,
        }
    )


def _resolve_temperature(temperature: float | None) -> float | None:
    if temperature is not None:
        return temperature

    raw_temperature = os.getenv("LLM_TEMPERATURE")
    if raw_temperature is None or raw_temperature.strip() == "":
        return None

    try:
        return float(raw_temperature)
    except ValueError:
        return None


def load_local_env(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from a local .env file if it exists."""
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
