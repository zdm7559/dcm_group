from __future__ import annotations

import argparse
import json

from agent.workflow import run_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AutoFix Agent once.")
    parser.add_argument("--repo-path", default=".", help="Repository root path.")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum repair attempts.")
    args = parser.parse_args()

    result = run_once(repo_path=args.repo_path, max_attempts=args.max_attempts)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
