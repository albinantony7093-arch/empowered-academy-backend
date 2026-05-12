
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import razorpay
import hmac
import hashlib
import logging
import json

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.payment import Payment
from app.models.course import Course, Enrollment
from app.models.user import User
from app.utils.mail import send_enrollment_confirmation_email
from app.schemas.payment import (
    CreatePaymentOrderRequest,
    CreatePaymentOrderResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
    PaymentOut
)

logger = logging.getLogger(__name__)
router = APIRouter()

TRIAL_DAYS = 4

razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def _now():
    return datetime.now(timezone.utc)


def _extract_card_info(payment_entity: dict) -> dict:
    """Pull card details from a Razorpay payment entity if present."""
    card = payment_entity.get("card") or {}
    return {
        "card_network": card.get("network"),
        "card_issuer": card.get("issuer"),
        "card_last4": card.get("last4"),
        "international": str(payment_entity.get("international", "")).lower() or None,
    }


@router.post("/create-order", response_model=CreatePaymentOrderResponse)
def create_payment_order(
    payload: CreatePaymentOrderRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Create a Razorpay order for course payment.

    Two flows:
    - direct_purchase=True  → pay without a trial; enrollment is created as "pending_payment"
                              and upgraded to "paid" on successful payment.
    - direct_purchase=False → student must already have a trial/locked enrollment.
    """
    course = db.query(Course).filter(
        Course.id == payload.course_id,
        Course.is_active == True
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == current_user.id,
        Enrollment.course_id == payload.course_id
    ).first()

    # ── Already paid ──────────────────────────────────────────────────────────
    if enrollment and enrollment.payment_status == "paid":
        raise HTTPException(status_code=409, detail="You have already paid for this course")

    # ── Direct purchase: create a placeholder enrollment if needed ────────────
    if payload.direct_purchase:
        if not enrollment:
            # Brand new direct purchase — no trial access, blocked until payment completes
            enrollment = Enrollment(
                user_id=current_user.id,
                course_id=course.id,
                payment_status="pending_payment",
                trial_ends_at=None,
            )
            db.add(enrollment)
            db.flush()
        elif enrollment.payment_status not in ["pending_payment", "locked", "trial"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot process payment for enrollment with status: {enrollment.payment_status}"
            )
        # If they already have a trial enrollment, keep it as-is — trial expiry governs access
    else:
        # ── Trial flow: enrollment must already exist ─────────────────────────
        if not enrollment:
            raise HTTPException(
                status_code=500,
                detail="Please enroll in the course first to start your free trial, or use direct purchase."
            )
        if enrollment.payment_status not in ["locked", "trial"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot process payment for enrollment with status: {enrollment.payment_status}"
            )

    # Return existing pending order if one exists
    existing_payment = db.query(Payment).filter(
        Payment.enrollment_id == enrollment.id,
        Payment.status == "created"
    ).first()
    if existing_payment:
        db.commit()  # commit the enrollment if it was just created
        return CreatePaymentOrderResponse(
            order_id=existing_payment.razorpay_order_id,
            amount=float(existing_payment.amount),
            currency=existing_payment.currency,
            razorpay_key_id=settings.RAZORPAY_KEY_ID
        )

    amount_in_paise = int(float(course.price) * 100)
    receipt = f"c{course.id[:8]}_u{current_user.id[:8]}"
    notes = {
        "course_id": course.id,
        "course_title": course.title,
        "user_id": current_user.id,
        "enrollment_id": enrollment.id,
        "direct_purchase": str(payload.direct_purchase),
    }

    try:
        razorpay_order = razorpay_client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": notes,
        })
    except Exception as e:
        logger.error(f"Failed to create Razorpay order: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create payment order. Please try again later.")

    payment = Payment(
        user_id=current_user.id,
        course_id=course.id,
        enrollment_id=enrollment.id,
        razorpay_order_id=razorpay_order["id"],
        amount=course.price,
        amount_due=razorpay_order.get("amount_due", 0) / 100,
        currency="INR",
        status="created",
        receipt=receipt,
        notes=notes,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return CreatePaymentOrderResponse(
        order_id=razorpay_order["id"],
        amount=float(course.price),
        currency="INR",
        razorpay_key_id=settings.RAZORPAY_KEY_ID
    )


@router.post("/verify", response_model=VerifyPaymentResponse)
def verify_payment(
    payload: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Verify Razorpay payment signature and update enrollment to paid."""
    payment = db.query(Payment).filter(
        Payment.razorpay_order_id == payload.razorpay_order_id,
        Payment.user_id == current_user.id
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    if payment.status == "paid":
        return VerifyPaymentResponse(
            success=True,
            message="Payment already verified",
            enrollment_id=payment.enrollment_id
        )

    # Verify HMAC signature
    generated_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    if generated_signature != payload.razorpay_signature:
        payment.status = "failed"
        payment.error_code = "SIGNATURE_MISMATCH"
        payment.error_description = "Invalid payment signature"
        payment.failed_at = _now()
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    # Fetch full payment details from Razorpay
    try:
        rz_payment = razorpay_client.payment.fetch(payload.razorpay_payment_id)
    except Exception as e:
        logger.warning(f"Could not fetch payment details from Razorpay: {e}")
        rz_payment = {}

    card_info = _extract_card_info(rz_payment)

    payment.razorpay_payment_id = payload.razorpay_payment_id
    payment.razorpay_signature = payload.razorpay_signature
    payment.status = "paid"
    payment.paid_at = _now()
    payment.payment_method = rz_payment.get("method")
    payment.bank = rz_payment.get("bank")
    payment.wallet = rz_payment.get("wallet")
    payment.vpa = rz_payment.get("vpa")
    payment.card_network = card_info["card_network"]
    payment.card_issuer = card_info["card_issuer"]
    payment.card_last4 = card_info["card_last4"]
    payment.international = card_info["international"]
    payment.contact = rz_payment.get("contact")
    payment.email = rz_payment.get("email")
    payment.amount_paid = rz_payment.get("amount", 0) / 100 if rz_payment.get("amount") else None

    enrollment = db.query(Enrollment).filter(Enrollment.id == payment.enrollment_id).first()
    if enrollment:
        enrollment.payment_status = "paid"
        enrollment.trial_ends_at = None  # clear trial timer if it was a trial enrollment

    db.commit()
    logger.info(f"Payment verified: order={payload.razorpay_order_id} payment={payload.razorpay_payment_id}")

    # Send enrollment confirmation email
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        course = db.query(Course).filter(Course.id == payment.course_id).first()
        if user and course:
            import asyncio
            asyncio.run(
                send_enrollment_confirmation_email(user.email, user.full_name or "", course.title)
            )
    except Exception as e:
        logger.warning(f"Failed to send enrollment email: {e}")

    return VerifyPaymentResponse(
        success=True,
        message="Payment verified successfully",
        enrollment_id=payment.enrollment_id
    )


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Razorpay webhook events."""
    webhook_signature = request.headers.get("X-Razorpay-Signature")
    if not webhook_signature:
        raise HTTPException(status_code=400, detail="Missing webhook signature")

    body = await request.body()

    # Verify webhook signature
    try:
        razorpay_client.utility.verify_webhook_signature(
            body.decode(),
            webhook_signature,
            settings.RAZORPAY_WEBHOOK_SECRET
        )
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    webhook_data = json.loads(body.decode())
    event = webhook_data.get("event")
    payment_entity = webhook_data.get("payload", {}).get("payment", {}).get("entity", {})
    dispute_entity = webhook_data.get("payload", {}).get("dispute", {}).get("entity", {})

    # ── payment.captured ──────────────────────────────────────────────────────
    if event == "payment.captured":
        order_id = payment_entity.get("order_id")
        payment_id = payment_entity.get("id")

        payment = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
        if payment and payment.status != "paid":
            card_info = _extract_card_info(payment_entity)
            payment.razorpay_payment_id = payment_id
            payment.status = "paid"
            payment.paid_at = _now()
            payment.payment_method = payment_entity.get("method")
            payment.bank = payment_entity.get("bank")
            payment.wallet = payment_entity.get("wallet")
            payment.vpa = payment_entity.get("vpa")
            payment.card_network = card_info["card_network"]
            payment.card_issuer = card_info["card_issuer"]
            payment.card_last4 = card_info["card_last4"]
            payment.international = card_info["international"]
            payment.contact = payment_entity.get("contact")
            payment.email = payment_entity.get("email")
            payment.amount_paid = payment_entity.get("amount", 0) / 100
            payment.webhook_payload = webhook_data

            enrollment = db.query(Enrollment).filter(Enrollment.id == payment.enrollment_id).first()
            if enrollment:
                enrollment.payment_status = "paid"
                enrollment.trial_ends_at = None

            db.commit()

            # Send enrollment confirmation email
            try:
                user = db.query(User).filter(User.id == payment.user_id).first()
                course = db.query(Course).filter(Course.id == payment.course_id).first()
                if user and course:
                    import asyncio
                    asyncio.create_task(
                        send_enrollment_confirmation_email(user.email, user.full_name or "", course.title)
                    )
            except Exception:
                pass

    # ── payment.failed ────────────────────────────────────────────────────────
    elif event == "payment.failed":
        order_id = payment_entity.get("order_id")
        payment_id = payment_entity.get("id")
        error_data = payment_entity.get("error", {})

        payment = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
        if payment:
            payment.razorpay_payment_id = payment_id
            payment.status = "failed"
            payment.failed_at = _now()
            payment.error_code = error_data.get("code") or payment_entity.get("error_code")
            payment.error_description = error_data.get("description") or payment_entity.get("error_description")
            payment.error_source = error_data.get("source") or payment_entity.get("error_source")
            payment.error_step = error_data.get("step") or payment_entity.get("error_step")
            payment.error_reason = error_data.get("reason") or payment_entity.get("error_reason")
            payment.payment_method = payment_entity.get("method")
            payment.contact = payment_entity.get("contact")
            payment.email = payment_entity.get("email")
            payment.webhook_payload = webhook_data
            db.commit()

    # ── payment.dispute.created ───────────────────────────────────────────────
    elif event == "payment.dispute.created":
        payment_id = payment_entity.get("id")
        payment = db.query(Payment).filter(Payment.razorpay_payment_id == payment_id).first()
        if payment:
            payment.status = "disputed"
            payment.dispute_id = dispute_entity.get("id")
            payment.dispute_reason = dispute_entity.get("reason_description") or dispute_entity.get("reason")
            payment.dispute_amount = dispute_entity.get("amount", 0) / 100
            payment.error_description = f"Dispute created: {payment.dispute_reason} (ID: {payment.dispute_id})"
            payment.webhook_payload = webhook_data

            enrollment = db.query(Enrollment).filter(Enrollment.id == payment.enrollment_id).first()
            if enrollment and enrollment.payment_status == "paid":
                enrollment.payment_status = "locked"

            db.commit()

    # ── payment.dispute.action_required ──────────────────────────────────────
    elif event == "payment.dispute.action_required":
        payment_id = payment_entity.get("id")
        payment = db.query(Payment).filter(Payment.razorpay_payment_id == payment_id).first()
        if payment:
            payment.dispute_id = dispute_entity.get("id") or payment.dispute_id
            payment.error_description = f"Dispute action required (ID: {payment.dispute_id})"
            payment.webhook_payload = webhook_data

            # Lock enrollment in case dispute.created was missed
            enrollment = db.query(Enrollment).filter(Enrollment.id == payment.enrollment_id).first()
            if enrollment and enrollment.payment_status == "paid":
                enrollment.payment_status = "locked"

            db.commit()

    # ── payment.dispute.won ───────────────────────────────────────────────────
    elif event == "payment.dispute.won":
        payment_id = payment_entity.get("id")
        payment = db.query(Payment).filter(Payment.razorpay_payment_id == payment_id).first()
        if payment:
            payment.status = "paid"
            payment.dispute_id = dispute_entity.get("id") or payment.dispute_id
            payment.error_description = f"Dispute won (ID: {payment.dispute_id})"
            payment.webhook_payload = webhook_data

            enrollment = db.query(Enrollment).filter(Enrollment.id == payment.enrollment_id).first()
            if enrollment:
                enrollment.payment_status = "paid"

            db.commit()

    # ── payment.dispute.lost ──────────────────────────────────────────────────
    elif event == "payment.dispute.lost":
        payment_id = payment_entity.get("id")
        payment = db.query(Payment).filter(Payment.razorpay_payment_id == payment_id).first()
        if payment:
            payment.status = "refunded"
            payment.refunded_at = _now()
            payment.dispute_id = dispute_entity.get("id") or payment.dispute_id
            payment.error_description = f"Dispute lost (ID: {payment.dispute_id})"
            payment.webhook_payload = webhook_data

            enrollment = db.query(Enrollment).filter(Enrollment.id == payment.enrollment_id).first()
            if enrollment:
                enrollment.payment_status = "cancelled"

            db.commit()

    # ── refund.processed ──────────────────────────────────────────────────────
    elif event == "refund.processed":
        refund_entity = webhook_data.get("payload", {}).get("refund", {}).get("entity", {})
        payment_id = refund_entity.get("payment_id")
        payment = db.query(Payment).filter(Payment.razorpay_payment_id == payment_id).first()
        if payment:
            payment.status = "refunded"
            payment.refunded_at = _now()
            payment.error_description = f"Refund processed: {refund_entity.get('id')}"
            payment.webhook_payload = webhook_data

            enrollment = db.query(Enrollment).filter(Enrollment.id == payment.enrollment_id).first()
            if enrollment and enrollment.payment_status == "paid":
                enrollment.payment_status = "cancelled"

            db.commit()

    else:
        pass

    return {"status": "ok"}


@router.get("/history", response_model=list[PaymentOut])
def get_payment_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Get payment history for current user."""
    payments = db.query(Payment).filter(
        Payment.user_id == current_user.id
    ).order_by(Payment.created_at.desc()).all()
    return payments
