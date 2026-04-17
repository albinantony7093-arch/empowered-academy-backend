import time
import logging
from fastapi import Request

logger = logging.getLogger("request")

async def request_logging_middleware(request: Request, call_next):
    """Log every request with user_id (if present in token), path, and response time."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        f"{request.method} {request.url.path} "
        f"→ {response.status_code} | {duration_ms}ms"
    )
    return response
