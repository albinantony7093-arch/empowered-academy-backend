from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import date
from pydantic import StringConstraints
from typing import Annotated

Name = Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
PhoneNumber = Annotated[str, StringConstraints(min_length=10, max_length=15, pattern=r"^\+?[\d\s\-\(\)]+$")]


class EnrolledCourse(BaseModel):
    enrollment_id: str
    payment_status: str
    course_id: str
    title: str
    description: str
    exam: str
    price: float
    keypoints: List[str]
    is_active: bool


class ProfileOut(BaseModel):
    user_id: str
    name: str
    email: str
    phone_number: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    target_exam: Optional[str] = None
    level: Optional[str] = None
    preferred_subjects: Optional[List[str]] = None
    study_goal: Optional[str] = None
    rank: Optional[int] = None
    average_score: Optional[float] = None
    tests_taken: int = 0
    enrolled_courses: List[EnrolledCourse] = []

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    full_name: Optional[Name] = None
    phone_number: Optional[PhoneNumber] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    target_exam: Optional[str] = None
    level: Optional[str] = None
    preferred_subjects: Optional[List[str]] = None
    study_goal: Optional[str] = None

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v):
        if v is not None and v not in ['Male', 'Female', 'Other']:
            raise ValueError('Gender must be Male, Female, or Other')
        return v