from sqlalchemy import Column, String, DateTime, Numeric, Boolean, ForeignKey, Text, Interval
from sqlalchemy.sql import func
from uuid_extensions import uuid7
from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid7()))
    title = Column(String, nullable=False)
    description = Column(Text)
    exam = Column(String, nullable=False, default="UG")  # "UG" or "PG"
    price = Column(Numeric(10, 2), nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid7()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False, index=True)
    # "trial" | "paid" | "locked" | "cancelled"
    payment_status = Column(String, nullable=False, default="trial")
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)  # enrolled_at + 4 days
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())
