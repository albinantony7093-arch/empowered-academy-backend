from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from app.core.database import Base


class Response(Base):
    """Per-answer row — one row per question per test attempt."""
    __tablename__ = "responses"

    id              = Column(Integer, primary_key=True, index=True)
    attempt_id      = Column(Integer, ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id     = Column(String, nullable=False)
    exam            = Column(String, nullable=False, index=True)   # "UG" | "PG"
    subject         = Column(String, nullable=True)
    topic           = Column(String, nullable=True, index=True)
    selected_answer = Column(String, nullable=True)
    correct_answer  = Column(String, nullable=True)
    is_correct      = Column(Boolean, nullable=False, default=False)
