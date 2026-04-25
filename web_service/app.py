from __future__ import annotations

from fastapi import FastAPI

from web_service.api.router import api_router
from web_service.core.error_handlers import unhandled_exception_handler


def create_app() -> FastAPI:
    application = FastAPI(title="AutoFix Demo Web Service")
    application.include_router(api_router)
    application.add_exception_handler(Exception, unhandled_exception_handler)
    return application


app = create_app()
