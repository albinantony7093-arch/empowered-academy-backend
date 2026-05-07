from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from uuid_extensions import uuid7
from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid7()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False, index=True)
    enrollment_id = Column(String, ForeignKey("enrollments.id"), nullable=False, index=True)

    # ── Razorpay IDs ──────────────────────────────────────────────────────────
    razorpay_order_id = Column(String, unique=True, nullable=False, index=True)
    razorpay_payment_id = Column(String, unique=True, nullable=True, index=True)
    razorpay_signature = Column(String, nullable=True)

    # ── Amount ────────────────────────────────────────────────────────────────
    amount = Column(Numeric(10, 2), nullable=False)          # INR
    amount_due = Column(Numeric(10, 2), nullable=True)       # from Razorpay order
    amount_paid = Column(Numeric(10, 2), nullable=True)      # confirmed paid amount
    currency = Column(String, nullable=False, default="INR")

    # ── Status & method ───────────────────────────────────────────────────────
    status = Column(String, nullable=False, default="created")
    # created | paid | failed | refunded | disputed | cancelled
    payment_method = Column(String, nullable=True)           # card | upi | netbanking | wallet
    bank = Column(String, nullable=True)                     # bank name if netbanking/card
    wallet = Column(String, nullable=True)                   # wallet name if wallet payment
    vpa = Column(String, nullable=True)                      # UPI VPA (e.g. user@upi)
    card_network = Column(String, nullable=True)             # Visa / Mastercard / RuPay etc.
    card_issuer = Column(String, nullable=True)              # issuing bank of card
    card_last4 = Column(String, nullable=True)               # last 4 digits of card
    international = Column(String, nullable=True)            # "true"/"false" — international card?

    # ── Customer contact captured at payment time ─────────────────────────────
    contact = Column(String, nullable=True)                  # phone number
    email = Column(String, nullable=True)                    # email used at checkout

    # ── Error details (on failure) ────────────────────────────────────────────
    error_code = Column(String, nullable=True)               # e.g. BAD_REQUEST_ERROR
    error_description = Column(Text, nullable=True)          # human-readable reason
    error_source = Column(String, nullable=True)             # customer | business | gateway
    error_step = Column(String, nullable=True)               # payment_authorization etc.
    error_reason = Column(String, nullable=True)             # e.g. payment_failed

    # ── Dispute details ───────────────────────────────────────────────────────
    dispute_id = Column(String, nullable=True, index=True)
    dispute_reason = Column(String, nullable=True)
    dispute_amount = Column(Numeric(10, 2), nullable=True)

    # ── Razorpay receipt & notes ──────────────────────────────────────────────
    receipt = Column(String, nullable=True)                  # receipt id sent to Razorpay
    notes = Column(JSON, nullable=True)                      # notes dict sent to Razorpay

    # ── Raw webhook payloads for full auditability ────────────────────────────
    # Stores the last raw webhook JSON received for this payment
    webhook_payload = Column(JSON, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)     # when payment was captured
    failed_at = Column(DateTime(timezone=True), nullable=True)   # when payment failed
    refunded_at = Column(DateTime(timezone=True), nullable=True) # when refund was processed
