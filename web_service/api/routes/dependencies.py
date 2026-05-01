from __future__ import annotations

from fastapi import APIRouter

from web_service.services.dependencies import load_wrong_import_path, load_yaml_dependency


router = APIRouter(prefix="/dependencies", tags=["bug-cases"])


@router.get("/missing-yaml")
async def missing_yaml() -> dict[str, str]:
    dependency = load_yaml_dependency()
    return {"module": dependency.__name__}


@router.get("/bad-import")
async def bad_import() -> dict[str, str]:
    dependency = load_wrong_import_path()
    return {"module": dependency.__name__}
