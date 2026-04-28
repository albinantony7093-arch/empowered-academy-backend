from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class CourseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    exam: str = Field(default="UG", pattern="^(UG|PG)$")
    price: Decimal = Field(default=Decimal("0"), ge=0)
    keypoints: Optional[List[str]] = None


class CourseOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    exam: str
    price: float
    keypoints: Optional[List[str]]
    is_active: bool
    created_by: str

    model_config = {"from_attributes": True}


class EnrollmentOut(BaseModel):
    id: str
    user_id: str
    course_id: str
    payment_status: str
    trial_ends_at: Optional[datetime]
    enrolled_at: datetime

    model_config = {"from_attributes": True}


class MyCourseOut(BaseModel):
    enrollment_id: str
    payment_status: str
    course_id: str
    title: str
    description: Optional[str]
    exam: str
    price: float
    keypoints: Optional[List[str]]
    is_active: bool

    model_config = {"from_attributes": True}
