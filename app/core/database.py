from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,          # persistent connections kept open
    max_overflow=40,       # extra connections allowed under burst (total 60)
    pool_timeout=30,       # seconds to wait for a connection before raising
    pool_pre_ping=True,    # discard stale connections automatically
    pool_recycle=1800,     # recycle connections every 30 min
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
