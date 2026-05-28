from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class CourseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    detailed_description: Optional[str] = None
    exam: str = Field(..., pattern="^(NEET UG|NEET PG|CRASH COURSE)$")
    price: Decimal = Field(default=Decimal("0"), ge=0)
    is_free: bool = False
    is_flagship: bool = False
    keypoints: Optional[List[str]] = None

    # Trial / free limits
    free_questions_per_test: Optional[int] = None
    free_daily_test_limit: Optional[int] = None
    free_trial_days: Optional[int] = None

    # Paid limits (ignored for crash course)
    questions_per_test: Optional[int] = None
    daily_test_limit: Optional[int] = None
    validity_days: Optional[int] = None  # NULL = lifetime


class CourseOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    detailed_description: Optional[str] = None
    exam: str
    price: float
    is_free: bool
    is_active: bool
    is_flagship: bool
    keypoints: Optional[List[str]]
    free_questions_per_test: Optional[int]
    free_daily_test_limit: Optional[int]
    free_trial_days: Optional[int]
    questions_per_test: Optional[int]
    daily_test_limit: Optional[int]
    validity_days: Optional[int]
    created_by: str

    # Per-user enrollment state (only when authenticated)
    is_enrolled: Optional[bool] = None
    payment_status: Optional[str] = None
    trial_ends_at: Optional[str] = None
    plan_expires_at: Optional[str] = None

    model_config = {"from_attributes": True}


class EnrollmentOut(BaseModel):
    id: str
    user_id: str
    course_id: str
    payment_status: str
    trial_ends_at: Optional[datetime]
    plan_expires_at: Optional[datetime]
    enrolled_at: datetime

    model_config = {"from_attributes": True}


class MyCourseOut(BaseModel):
    enrollment_id: str
    payment_status: str
    trial_ends_at: Optional[datetime]
    plan_expires_at: Optional[datetime]
    course_id: str
    title: str
    description: Optional[str]
    exam: str
    price: float
    is_free: bool
    is_active: bool
    is_flagship: bool
    keypoints: Optional[List[str]]
    free_questions_per_test: Optional[int]
    free_daily_test_limit: Optional[int]
    free_trial_days: Optional[int]
    questions_per_test: Optional[int]
    daily_test_limit: Optional[int]
    validity_days: Optional[int]

    model_config = {"from_attributes": True}
