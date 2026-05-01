from __future__ import annotations

from pathlib import Path


def read_missing_config() -> str:
    return Path("config.json").read_text(encoding="utf-8")


def write_log_in_missing_dir() -> None:
    Path("logs/missing-dir").mkdir(parents=True, exist_ok=True)
    Path("logs/missing-dir/app.log").write_text("started\n", encoding="utf-8")
