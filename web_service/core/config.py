from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"
ERROR_LOG_PATH = LOG_DIR / "error.log"
SERVICE_NAME = "demo-web-service"

