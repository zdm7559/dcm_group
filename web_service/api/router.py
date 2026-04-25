from __future__ import annotations

from fastapi import APIRouter

from web_service.api.routes import calculator, health, users


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(calculator.router)
api_router.include_router(users.router)

