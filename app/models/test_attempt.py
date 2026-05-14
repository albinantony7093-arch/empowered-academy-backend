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
    user_id      = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    test_id      = Column(String, unique=True, nullable=False, index=True)
    exam         = Column(String, nullable=False, default="NEET UG")  # "NEET UG" or "NEET PG"
    course_id    = Column(String, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)
    status       = Column(String, default=AttemptStatus.generated, nullable=False)
    score        = Column(Float, nullable=True)   # number of correct answers
    marks        = Column(Float, nullable=True)   # weighted marks (easy=1, medium=2, hard=3)
    max_marks    = Column(Float, nullable=True)   # total possible marks
    accuracy     = Column(Float, nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)
