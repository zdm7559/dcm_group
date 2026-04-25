from __future__ import annotations

import argparse
import urllib.error
import urllib.request


BUG_PATHS = {
    "divide": "/divide?a=10&b=0",
    "user": "/users/999",
}


def request_url(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "case",
        choices=sorted(BUG_PATHS),
        help="Bug case to trigger.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Running web service base URL.",
    )
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + BUG_PATHS[args.case]
    status, body = request_url(url)

    print(f"{args.case}: {url}")
    print(f"status: {status}")
    print(body)


if __name__ == "__main__":
    main()

