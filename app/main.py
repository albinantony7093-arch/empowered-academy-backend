import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
from app.core.database import Base, engine
from app.routes import auth, test, ai, courses as courses_router, profile as profile_router
from app.routes import analytics as analytics_router
from app.middleware.logging import request_logging_middleware

import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Empowered Academy API", version="1.3.0")


def _register_models() -> None:
    """
    Import every ORM model so SQLAlchemy's metadata is aware of all tables
    before Base.metadata.create_all() is called.
    Imports are intentionally side-effect-only.
    """
    import app.models.user as _u; assert _u
    import app.models.user_profile as _up; assert _up
    import app.models.test_attempt as _ta; assert _ta
    import app.models.analytics as _a; assert _a
    import app.models.response as _r; assert _r
    import app.models.otp as _o; assert _o
    import app.models.course as _c; assert _c


_register_models()
try:
    Base.metadata.create_all(bind=engine, checkfirst=True)
except Exception as _db_err:
    logger.error(f"Could not create DB tables at startup: {_db_err}")

# Pre-load question datasets into memory at startup — avoids cold-start lag
# under concurrent first requests
from app.utils.question_engine import load_exam as _load_exam
try:
    _load_exam("UG")
    _load_exam("PG")
except Exception as _e:
    logger.warning(f"Could not pre-load question datasets: {_e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(request_logging_middleware)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    message = detail.get("message", str(detail)) if isinstance(detail, dict) else detail
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": message},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    messages = []
    for e in errors:
        loc = " -> ".join(str(l) for l in e.get("loc", []) if l != "body")
        msg = e.get("msg", "Invalid value")
        messages.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(
        status_code=422,
        content={"message": messages[0] if len(messages) == 1 else "; ".join(messages)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled error on {request.method} {request.url}: {exc}", exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"message": "Something went wrong on our end. Please try again later."},
    )


def _status_label(code: int) -> str:
    return {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        410: "Gone",
        422: "Validation Error",
        429: "Too Many Requests",
        503: "Service Unavailable",
    }.get(code, "Error")


app.include_router(auth.router,             prefix="/auth",      tags=["auth"])
app.include_router(test.router,             prefix="/test",      tags=["test"])
app.include_router(analytics_router.router, prefix="/analytics", tags=["analytics"])
app.include_router(ai.router,               prefix="/ai",        tags=["ai"])
app.include_router(courses_router.router,   prefix="/courses",   tags=["courses"])
app.include_router(profile_router.router,   prefix="/profile",   tags=["profile"])


@app.get("/health", tags=["ops"])
def health_check():
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unreachable"
    return {"status": "ok", "version": "1.3.0", "db": db_status}

