from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class TestResult(Base):
    __tablename__ = "test_results"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_id = Column(Integer, ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    subject    = Column(String, nullable=False)   # stores "UG" or "PG" at aggregate level
    score      = Column(Float, nullable=True)
    weak_areas = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
