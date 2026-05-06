from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class CreatePaymentOrderRequest(BaseModel):
    course_id: str = Field(..., description="Course ID to purchase")


class CreatePaymentOrderResponse(BaseModel):
    order_id: str
    amount: float
    currency: str
    razorpay_key_id: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyPaymentResponse(BaseModel):
    success: bool
    message: str
    enrollment_id: Optional[str] = None


class PaymentOut(BaseModel):
    id: str
    user_id: str
    course_id: str
    enrollment_id: str
    razorpay_order_id: str
    razorpay_payment_id: Optional[str]
    amount: float
    currency: str
    status: str
    payment_method: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
