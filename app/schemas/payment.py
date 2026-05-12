from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any, Dict


class CreatePaymentOrderRequest(BaseModel):
    course_id: str = Field(..., description="Course ID to purchase")
    direct_purchase: bool = Field(
        default=False,
        description="If True, pay directly without a trial enrollment first"
    )


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

    # Razorpay IDs
    razorpay_order_id: str
    razorpay_payment_id: Optional[str] = None

    # Amount
    amount: float
    amount_due: Optional[float] = None
    amount_paid: Optional[float] = None
    currency: str

    # Status & method
    status: str
    payment_method: Optional[str] = None
    bank: Optional[str] = None
    wallet: Optional[str] = None
    vpa: Optional[str] = None
    card_network: Optional[str] = None
    card_issuer: Optional[str] = None
    card_last4: Optional[str] = None
    international: Optional[str] = None

    # Customer
    contact: Optional[str] = None
    email: Optional[str] = None

    # Error
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    error_source: Optional[str] = None
    error_step: Optional[str] = None
    error_reason: Optional[str] = None

    # Dispute
    dispute_id: Optional[str] = None
    dispute_reason: Optional[str] = None
    dispute_amount: Optional[float] = None

    # Receipt & notes
    receipt: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    paid_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None

    class Config:
        from_attributes = True
