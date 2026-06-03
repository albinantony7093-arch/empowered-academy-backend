from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class DiagnosticStatus(str, enum.Enum):
    generated = "generated"
    submitted  = "submitted"


class DiagnosticAttempt(Base):
    __tablename__ = "diagnostic_attempts"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    test_id      = Column(String, unique=True, nullable=False, index=True)
    status       = Column(String, default=DiagnosticStatus.generated, nullable=False)
    score        = Column(Float, nullable=True)      # number of correct answers
    marks        = Column(Float, nullable=True)      # weighted marks
    max_marks    = Column(Float, nullable=True)      # total possible marks
    accuracy     = Column(Float, nullable=True)
    questions    = Column(Text, nullable=True)       # JSON: [{question_id, difficulty}]
    responses    = Column(JSON, nullable=True)       # per-answer breakdown stored inline
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)
