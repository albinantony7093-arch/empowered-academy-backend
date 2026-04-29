from sqlalchemy import Column, String, Date, ForeignKey
from app.core.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    phone_number = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String, nullable=True)  # "Male", "Female", "Other"
    target_exam = Column(String, nullable=True)  # "NEET UG", "NEET PG", etc.
    level = Column(String, nullable=True)  # "Class 12", "Graduate", etc.
    preferred_subjects = Column(String, nullable=True)  # JSON string of subjects
    study_goal = Column(String, nullable=True)