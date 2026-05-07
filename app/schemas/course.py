from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class CourseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    detailed_description: Optional[str] = None
    exam: str = Field(default="UG", pattern="^(UG|PG)$")
    price: Decimal = Field(default=Decimal("2000"), ge=0)
    keypoints: Optional[List[str]] = None


class CourseOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    detailed_description: Optional[str] = None
    exam: str
    price: float
    keypoints: Optional[List[str]]
    is_active: bool
    is_flagship: bool = False
    created_by: str
    is_enrolled: Optional[bool] = None
    payment_status: Optional[str] = None  # trial | locked | paid | cancelled
    trial_ends_at: Optional[str] = None

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
    detailed_description: Optional[str] = None
    exam: str
    price: float
    keypoints: Optional[List[str]]
    is_active: bool
    is_flagship: bool = False

    model_config = {"from_attributes": True}
