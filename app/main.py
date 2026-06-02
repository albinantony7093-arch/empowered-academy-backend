import logging
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
from app.core.database import Base, engine
from app.routes import auth, test, ai, courses as courses_router, profile as profile_router
from app.routes import analytics as analytics_router, payment as payment_router
from app.middleware.logging import request_logging_middleware

import signal
import sys
import asyncio
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Sentry — only initialises when DSN is set (safe to leave blank in local dev)
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        send_default_pii=False,
        traces_sample_rate=1.0,
        profile_session_sample_rate=1.0,
        profile_lifecycle="trace",
    )
    logger.info("Sentry initialised")

app = FastAPI(title="Empowered Academy API", version="1.3.0", docs_url=None, redoc_url=None, openapi_url=None)


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
    import app.models.payment as _p; assert _p


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
    allow_credentials=True,
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
app.include_router(payment_router.router,   prefix="/payment",   tags=["payment"])


# ── Crash Course Scheduler ────────────────────────────────────────────────────

_scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
_crash_course_notified = False  # in-process guard so email fires only once


async def _crash_course_tick() -> None:
    """
    Runs every minute. When the current time enters the crash course window:
      1. Sets is_active = True on the Crash Course row.
      2. Emails every student account exactly once.
    When the window ends:
      1. Sets is_active = False.
    """
    global _crash_course_notified

    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(settings.CRASH_COURSE_START)
    end   = datetime.fromisoformat(settings.CRASH_COURSE_END)

    # Normalise to UTC if offset-aware
    if start.tzinfo is not None:
        start = start.astimezone(timezone.utc)
    if end.tzinfo is not None:
        end = end.astimezone(timezone.utc)

    from app.core.database import SessionLocal
    from app.models.course import Course
    from app.models.user import User
    from app.utils.mail import send_crash_course_live_email

    db = SessionLocal()
    try:
        course = db.query(Course).filter(Course.title == "Crash Course").first()
        if not course:
            return

        if start <= now <= end:
            # Activate if not already
            if not course.is_active:
                course.is_active = True
                db.commit()
                logger.info("Crash Course activated")

            # Send emails exactly once — use DB flag to guard across all workers
            if not _crash_course_notified:
                from sqlalchemy import text
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT pg_try_advisory_lock(123456789)"))
                    got_lock = result.scalar()

                if not got_lock:
                    logger.info("Another worker is sending crash course emails — skipping")
                    _crash_course_notified = True
                    return
                ends_local = end.astimezone(
                    datetime.fromisoformat(settings.CRASH_COURSE_END).tzinfo
                )
                ends_str = ends_local.strftime("%-d %B %Y at %-I:%M %p IST")

                students = db.query(User).filter(User.role == "student").all()
                logger.info("Sending crash course live emails to %d students", len(students))

                for user in students:
                    try:
                        await send_crash_course_live_email(
                            email=user.email,
                            full_name=user.full_name or "Student",
                            ends_at=ends_str,
                        )
                    except Exception as mail_err:
                        logger.warning("Could not email %s: %s", user.email, mail_err)

                _crash_course_notified = True
                logger.info("Crash course live emails sent")

        else:
            # Outside window — deactivate
            if course.is_active:
                course.is_active = False
                db.commit()
                logger.info("Crash Course deactivated")
            # Reset flag so it fires again if dates are updated
            if now > end:
                _crash_course_notified = False

    except Exception as e:
        logger.error("crash_course_tick error: %s", e, exc_info=True)
        db.rollback()
    finally:
        db.close()


@app.on_event("startup")
async def start_scheduler() -> None:
    _scheduler.add_job(_crash_course_tick, "interval", minutes=1, id="crash_course_tick")
    _scheduler.start()
    logger.info("Crash course scheduler started")


@app.on_event("shutdown")
async def stop_scheduler() -> None:
    _scheduler.shutdown(wait=False)


# ── Health check ──────────────────────────────────────────────────────────────

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
# TODO: Remove this route after verifying Sentry is working
@app.get("/sentry-debug", tags=["ops"])
async def trigger_error():
    division_by_zero = 1 / 0

