from sqlalchemy import Column, String, DateTime, Numeric, Boolean, ForeignKey, Text, JSON, Integer
from sqlalchemy.sql import func
from uuid_extensions import uuid7
from app.core.database import Base


class Course(Base):
    """
    Represents a single purchasable course card shown in the UI.

    Each plan (GOLD, PLATINUM) is its own Course row — they share the same
    exam category but have different prices, limits, and validity.

    Examples of rows in this table:
        title="NEET UG GOLD",     exam="NEET UG",     is_free=False
        title="NEET UG PLATINUM", exam="NEET UG",     is_free=False
        title="NEET PG GOLD",     exam="NEET PG",     is_free=False
        title="NEET PG PLATINUM", exam="NEET PG",     is_free=False
        title="Crash Course",     exam="CRASH COURSE", is_free=True

    The frontend groups courses by exam to show them under category headers.
    """
    __tablename__ = "courses"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid7()))
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    detailed_description = Column(Text, nullable=True)

    # Exam category — used by frontend to group course cards
    # "NEET UG" | "NEET PG" | "CRASH COURSE"
    exam = Column(String, nullable=False)

    # Price of this course (0 for free courses)
    price = Column(Numeric(10, 2), nullable=False, default=0)

    # True  = Crash Course — student gets "free" status, no payment ever
    # False = NEET UG/PG   — student gets "trial" status, must pay to continue
    is_free = Column(Boolean, nullable=False, default=False)

    is_active = Column(Boolean, nullable=False, default=True)
    is_flagship = Column(Boolean, nullable=False, default=False)
    keypoints = Column(JSON, nullable=True)

    # ── Trial / Free limits ───────────────────────────────────────────────────
    # For paid courses (NEET UG/PG): applied during the trial period only
    # For Crash Course: permanent limits for the entire access window
    free_questions_per_test = Column(Integer, nullable=True)  # NULL = unlimited
    free_daily_test_limit = Column(Integer, nullable=True)    # NULL = unlimited
    free_trial_days = Column(Integer, nullable=True)          # trial duration or crash course validity

    # ── Paid limits (after payment) ───────────────────────────────────────────
    # Only relevant for paid courses. NULL = unlimited.
    questions_per_test = Column(Integer, nullable=True)
    daily_test_limit = Column(Integer, nullable=True)

    # How long paid access lasts. NULL = lifetime (never expires).
    validity_days = Column(Integer, nullable=True)

    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Enrollment(Base):
    """
    Tracks a student's access state for a specific course.

    One enrollment per (user, course) pair. The payment_status field
    drives all access control decisions.

    Status flow for paid courses (NEET UG/PG):
        trial → paid       (student pays)
        trial → locked     (trial expires without payment)
        paid  → locked     (plan expires, if validity_days is set)

    Status flow for free courses (Crash Course):
        free  → locked     (free_trial_days window expires)
    """
    __tablename__ = "enrollments"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid7()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False, index=True)

    # "trial"           → on trial, free limits apply, expires at trial_ends_at
    # "free"            → crash course access, free limits apply, expires at trial_ends_at
    # "paid"            → paid access, course paid limits apply
    # "locked"          → no access (trial/free/plan expired, or manually locked)
    # "cancelled"       → no access, cancelled by student or admin
    # "pending_payment" → payment initiated but not yet confirmed by webhook
    payment_status = Column(String, nullable=False, default="trial")

    # Set on enrollment → enrolled_at + free_trial_days (end of day)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)

    # Set on payment → paid_at + validity_days (NULL if lifetime access)
    plan_expires_at = Column(DateTime(timezone=True), nullable=True)

    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())
