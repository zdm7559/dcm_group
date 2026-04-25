from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse

from web_service.core.config import SERVICE_NAME
from web_service.core.logging import get_error_logger


BUG_BLOCK_START = "=== AUTO_FIX_BUG_START ==="
BUG_BLOCK_END = "=== AUTO_FIX_BUG_END ==="


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    error_block = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": SERVICE_NAME,
        "method": request.method,
        "path": request.url.path,
        "path_params": request.path_params,
        "query": dict(request.query_params),
        "status_code": 500,
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "traceback": traceback.format_exc(),
    }

    logger = get_error_logger()
    logger.error(BUG_BLOCK_START)
    logger.error(json.dumps(error_block, ensure_ascii=False, indent=2))
    logger.error(BUG_BLOCK_END)

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal server error",
            "exception_type": type(exc).__name__,
        },
    )
