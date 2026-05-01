from __future__ import annotations

from fastapi import APIRouter

from web_service.api.routes import (
    calculator,
    config,
    dependencies,
    files,
    health,
    naming,
    profiles,
    requests,
    resources,
    users,
    validation_cases,
)


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(calculator.router)
api_router.include_router(users.router)
api_router.include_router(requests.router)
api_router.include_router(files.router)
api_router.include_router(config.router)
api_router.include_router(dependencies.router)
api_router.include_router(naming.router)
api_router.include_router(profiles.router)
api_router.include_router(resources.router)
api_router.include_router(validation_cases.router)
