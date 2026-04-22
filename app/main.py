import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import Base, engine
from app.routes import auth, test, ai
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
    import app.models.test_attempt as _ta; assert _ta
    import app.models.analytics as _a; assert _a
    import app.models.response as _r; assert _r
    import app.models.otp as _o; assert _o


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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled error on {request.method} {request.url}: {exc}", exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error. Please try again later."},
    )


app.include_router(auth.router,             prefix="/auth",      tags=["auth"])
app.include_router(test.router,             prefix="/test",      tags=["test"])
app.include_router(analytics_router.router, prefix="/analytics", tags=["analytics"])
app.include_router(ai.router,               prefix="/ai",        tags=["ai"])


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

