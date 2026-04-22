from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class AttemptStatus(str, enum.Enum):
    generated = "generated"
    submitted  = "submitted"


class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    test_id      = Column(String, unique=True, nullable=False, index=True)
    exam         = Column(String, nullable=False)
    status       = Column(String, default=AttemptStatus.generated, nullable=False)  # stored as plain string
    score        = Column(Float, nullable=True)
    accuracy     = Column(Float, nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)
