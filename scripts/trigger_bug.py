from __future__ import annotations

import argparse
import urllib.error
import urllib.request


BUG_CASES = {
    "divide": {
        "method": "GET",
        "path": "/divide?a=10&b=0",
    },
    "user": {
        "method": "GET",
        "path": "/users/999",
    },
    "invalid-json": {
        "method": "POST",
        "path": "/request/invalid-json",
        "body": "{bad json}",
        "headers": {"Content-Type": "application/json"},
    },
    "missing-config": {
        "method": "GET",
        "path": "/files/missing-config",
    },
    "missing-log-dir": {
        "method": "GET",
        "path": "/files/missing-log-dir",
    },
    "missing-api-key": {
        "method": "GET",
        "path": "/config/missing-api-key",
    },
    "invalid-timeout": {
        "method": "GET",
        "path": "/config/invalid-timeout",
    },
    "missing-yaml": {
        "method": "GET",
        "path": "/dependencies/missing-yaml",
    },
    "bad-import": {
        "method": "GET",
        "path": "/dependencies/bad-import",
    },
    "unknown-function": {
        "method": "GET",
        "path": "/naming/unknown-function",
    },
    "missing-profile": {
        "method": "GET",
        "path": "/data/missing-profile",
    },
    "not-found-as-500": {
        "method": "GET",
        "path": "/resources/not-found-as-500",
    },
    "missing-required": {
        "method": "GET",
        "path": "/validation/missing-required?name=Alice",
    },
    "bad-age": {
        "method": "GET",
        "path": "/validation/bad-age?age=abc",
    },
    "bad-range": {
        "method": "GET",
        "path": "/validation/bad-range?page=-1&limit=0",
    },
    "empty-username": {
        "method": "GET",
        "path": "/validation/empty-username?username=",
    },
    "missing-user-null": {
        "method": "GET",
        "path": "/nulls/missing-user",
    },
    "none-email": {
        "method": "GET",
        "path": "/nulls/none-email",
    },
    "missing-body-age": {
        "method": "POST",
        "path": "/body/missing-age",
        "body": "{\"name\":\"Alice\"}",
        "headers": {"Content-Type": "application/json"},
    },
    "int-string": {
        "method": "GET",
        "path": "/conversion/int-string?value=abc",
    },
    "float-string": {
        "method": "GET",
        "path": "/conversion/float-string?value=hello",
    },
    "bad-date": {
        "method": "GET",
        "path": "/conversion/bad-date?date=2026-99-99",
    },
}


def request_url(
    url: str,
    *,
    method: str = "GET",
    body: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        data=body.encode("utf-8") if body is not None else None,
        headers=headers or {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "case",
        choices=sorted(BUG_CASES),
        help="Bug case to trigger.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Running web service base URL.",
    )
    args = parser.parse_args()

    case = BUG_CASES[args.case]
    url = args.base_url.rstrip("/") + case["path"]
    status, body = request_url(
        url,
        method=case.get("method", "GET"),
        body=case.get("body"),
        headers=case.get("headers"),
    )

    print(f"{args.case}: {url}")
    print(f"method: {case.get('method', 'GET')}")
    print(f"status: {status}")
    print(body)


if __name__ == "__main__":
    main()
