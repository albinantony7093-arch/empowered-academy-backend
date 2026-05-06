from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.sql import func
from uuid_extensions import uuid7
from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid7()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False, index=True)
    enrollment_id = Column(String, ForeignKey("enrollments.id"), nullable=False, index=True)
    
    # Razorpay details
    razorpay_order_id = Column(String, unique=True, nullable=False, index=True)
    razorpay_payment_id = Column(String, unique=True, nullable=True, index=True)
    razorpay_signature = Column(String, nullable=True)
    
    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)  # Amount in INR
    currency = Column(String, nullable=False, default="INR")
    status = Column(String, nullable=False, default="created")  # created | paid | failed | refunded | disputed
    
    # Metadata
    payment_method = Column(String, nullable=True)  # card | netbanking | upi | wallet
    error_description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
