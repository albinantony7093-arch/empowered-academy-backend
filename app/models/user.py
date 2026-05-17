from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from uuid_extensions import uuid7
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid7()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    phone_number = Column(String, nullable=True)
    role = Column(String, nullable=False, default="student")  # "student" | "admin"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
