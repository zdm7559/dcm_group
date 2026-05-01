from __future__ import annotations

from fastapi import APIRouter

from web_service.services.files import read_missing_config, write_log_in_missing_dir


router = APIRouter(prefix="/files", tags=["bug-cases"])


@router.get("/missing-config")
async def missing_config() -> dict[str, str]:
    return {"content": read_missing_config()}


@router.get("/missing-log-dir")
async def missing_log_dir() -> dict[str, str]:
    write_log_in_missing_dir()
    return {"status": "ok"}
