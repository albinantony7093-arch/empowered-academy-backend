import uuid
import hmac
import hashlib
import base64
import logging
import json
import asyncio

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone

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
    VerifyPaymentResponse,
    PaymentOut,
)

logger = logging.getLogger(__name__)
router = APIRouter()

TRIAL_DAYS = 4


def _now():
    return datetime.now(timezone.utc)


def _cashfree_base_url() -> str:
    if settings.CASHFREE_ENV == "production":
        return "https://api.cashfree.com/pg"
    return "https://sandbox.cashfree.com/pg"


def _cashfree_headers() -> dict:
    return {
        "x-client-id": settings.CASHFREE_APP_ID,
        "x-client-secret": settings.CASHFREE_SECRET_KEY,
        "x-api-version": "2023-08-01",
        "Content-Type": "application/json",
    }


def _verify_webhook_signature(timestamp: str, raw_body: str, received_signature: str) -> bool:
    """Verify Cashfree webhook signature per their official docs."""
    signed_payload = timestamp + raw_body
    secret = settings.CASHFREE_WEBHOOK_SECRET or settings.CASHFREE_SECRET_KEY
    generated = base64.b64encode(
        hmac.new(
            secret.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).digest()
    ).decode()
    return hmac.compare_digest(generated, received_signature)


def _extract_card_info(payment_data: dict) -> dict:
    """Pull card details from a Cashfree payment object if present."""
    card = payment_data.get("payment_method", {}).get("card") or {}
    return {
        "card_network": card.get("card_network"),
        "card_issuer": card.get("card_bank_name"),
        "card_last4": card.get("card_number", "")[-4:] or None,
        "international": str(card.get("card_country", "") != "IN").lower() if card.get("card_country") else None,
    }


def _unlock_enrollment(db: Session, payment: Payment) -> None:
    """Mark enrollment as paid and set expiry based on course validity_days."""
    from datetime import timedelta
    enrollment = db.query(Enrollment).filter(Enrollment.id == payment.enrollment_id).first()
    if not enrollment:
        return
    enrollment.payment_status = "paid"
    enrollment.trial_ends_at = None

    course = db.query(Course).filter(Course.id == payment.course_id).first()
    if course and course.validity_days:
        enrollment.plan_expires_at = _now() + timedelta(days=course.validity_days)
    else:
        enrollment.plan_expires_at = None  # lifetime


async def _send_confirmation_email(db: Session, payment: Payment, order_id: str) -> None:
    try:
        user = db.query(User).filter(User.id == payment.user_id).first()
        course = db.query(Course).filter(Course.id == payment.course_id).first()
        if user and course:
            await send_enrollment_confirmation_email(
                email=user.email,
                full_name=user.full_name or "",
                course_title=course.title,
                course_id=course.id,
                transaction_id=order_id,
            )
    except Exception as e:
        logger.warning(f"Failed to send enrollment email: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# POST /payment/create-order
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/create-order", response_model=CreatePaymentOrderResponse)
async def create_payment_order(
    payload: CreatePaymentOrderRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Create a Cashfree order and return payment_session_id for the JS SDK.

    Two flows:
    - direct_purchase=True  → pay without a trial; enrollment created as "pending_payment".
    - direct_purchase=False → student must already have a trial/locked enrollment.
    """
    course = db.query(Course).filter(
        Course.id == payload.course_id,
        Course.is_active == True,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    amount = float(course.price)

    enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == current_user.id,
        Enrollment.course_id == payload.course_id,
    ).first()

    if enrollment and enrollment.payment_status == "paid":
        raise HTTPException(status_code=409, detail="You have already paid for this course")

    if payload.direct_purchase:
        if not enrollment:
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
                detail=f"Cannot process payment for enrollment with status: {enrollment.payment_status}",
            )
    else:
        if not enrollment:
            raise HTTPException(
                status_code=400,
                detail="Please enroll in the course first to start your free trial, or use direct purchase.",
            )
        if enrollment.payment_status not in ["locked", "trial"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot process payment for enrollment with status: {enrollment.payment_status}",
            )

    # Return existing pending order if one exists (idempotency)
    existing = db.query(Payment).filter(
        Payment.enrollment_id == enrollment.id,
        Payment.status == "created",
    ).first()
    if existing:
        db.commit()
        return CreatePaymentOrderResponse(
            order_id=existing.cf_order_id,
            payment_session_id=existing.payment_session_id or "",
            amount=float(existing.amount),
            currency=existing.currency,
        )

    # Generate a unique order ID before hitting Cashfree (save PENDING first)
    order_id = str(uuid.uuid4())

    # Save PENDING record before calling Cashfree — prevents lost payments
    payment = Payment(
        user_id=current_user.id,
        course_id=course.id,
        enrollment_id=enrollment.id,
        cf_order_id=order_id,
        amount=amount,
        currency="INR",
        status="created",
        receipt=f"c{course.id[:8]}_u{current_user.id[:8]}",
        notes={
            "course_id": course.id,
            "course_title": course.title,
            "user_id": current_user.id,
            "enrollment_id": enrollment.id,
            "direct_purchase": str(payload.direct_purchase),
        },
    )
    db.add(payment)
    db.flush()  # get the row in DB before external call

    # Call Cashfree Orders API
    cf_payload = {
        "order_id": order_id,
        "order_amount": amount,
        "order_currency": "INR",
        "customer_details": {
            "customer_id": current_user.id,
            "customer_phone": getattr(current_user, "phone", "9999999999") or "9999999999",
            "customer_email": getattr(current_user, "email", "") or "",
            "customer_name": getattr(current_user, "full_name", "") or "",
        },
        "order_meta": {
            "return_url": f"{settings.FRONTEND_URL}/payment-success?order_id={order_id}",
        },
        "order_note": f"Course: {course.title}",
    }

    cf_data = None
    last_exc = None
    for attempt in range(1, 4):  # up to 3 attempts
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_cashfree_base_url()}/orders",
                    json=cf_payload,
                    headers=_cashfree_headers(),
                )
            resp.raise_for_status()
            cf_data = resp.json()
            break
        except Exception as e:
            last_exc = e
            logger.warning(f"Cashfree order attempt {attempt} failed: {e}")
            if attempt < 3:
                await asyncio.sleep(2 ** attempt)  # 2s, 4s backoff

    if cf_data is None:
        logger.error(f"Failed to create Cashfree order after 3 attempts: {last_exc}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create payment order. Please try again later.")

    payment_session_id = cf_data.get("payment_session_id", "")
    payment.payment_session_id = payment_session_id
    db.commit()
    db.refresh(payment)

    logger.info(f"Cashfree order created: order_id={order_id}")

    return CreatePaymentOrderResponse(
        order_id=order_id,
        payment_session_id=payment_session_id,
        amount=amount,
        currency="INR",
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /payment/webhook  (Cashfree → Backend)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def cashfree_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle Cashfree webhook events.
    Cashfree is the authoritative source — do NOT trust frontend redirects.
    """
    logger.info("Cashfree webhook received")

    timestamp = request.headers.get("x-webhook-timestamp", "")
    received_signature = request.headers.get("x-webhook-signature", "")

    if not timestamp or not received_signature:
        logger.warning("Webhook rejected: missing signature headers")
        raise HTTPException(status_code=400, detail="Missing webhook signature headers")

    body_bytes = await request.body()
    raw_body = body_bytes.decode()

    logger.debug(f"Webhook raw body: {raw_body}")

    if not _verify_webhook_signature(timestamp, raw_body, received_signature):
        logger.warning("Webhook rejected: signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    logger.info("Webhook signature verified OK")

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("Webhook rejected: invalid JSON body")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type = data.get("type", "")
    order_data = data.get("data", {}).get("order", {})
    payment_data = data.get("data", {}).get("payment", {})

    order_id = order_data.get("order_id") or payment_data.get("order_id")
    cf_payment_id = str(payment_data.get("cf_payment_id", "")) or None
    payment_status = payment_data.get("payment_status", "")  # SUCCESS | FAILED | USER_DROPPED | etc.

    logger.info(f"Webhook event_type={event_type} order_id={order_id} cf_payment_id={cf_payment_id} payment_status={payment_status}")

    if not order_id:
        logger.warning("Webhook received with no order_id, ignoring")
        return {"status": "ok"}

    payment = db.query(Payment).filter(Payment.cf_order_id == order_id).first()
    if not payment:
        logger.warning(f"Webhook received for unknown order_id: {order_id}")
        return {"status": "ok"}

    # ── Idempotency guard ─────────────────────────────────────────────────────
    if payment.status == "paid":
        logger.info(f"Webhook ignored: order {order_id} already marked paid")
        return {"status": "ok"}

    payment.webhook_payload = data

    if event_type == "PAYMENT_SUCCESS_WEBHOOK" or payment_status == "SUCCESS":
        logger.info(f"Processing SUCCESS for order {order_id}, amount={payment_data.get('payment_amount')}, method={payment_data.get('payment_group')}")
        card_info = _extract_card_info(payment_data)
        payment.cf_payment_id = cf_payment_id
        payment.status = "paid"
        payment.paid_at = _now()
        payment.payment_method = payment_data.get("payment_group")  # UPI / CARD / NB / WALLET
        payment.bank = payment_data.get("bank_reference")
        payment.vpa = (payment_data.get("payment_method", {}) or {}).get("upi", {}).get("upi_id")
        payment.card_network = card_info["card_network"]
        payment.card_issuer = card_info["card_issuer"]
        payment.card_last4 = card_info["card_last4"]
        payment.international = card_info["international"]
        payment.contact = payment_data.get("customer_details", {}).get("customer_phone")
        payment.email = payment_data.get("customer_details", {}).get("customer_email")
        payment.amount_paid = payment_data.get("payment_amount")

        _unlock_enrollment(db, payment)
        db.commit()
        logger.info(f"Payment {order_id} marked paid, enrollment unlocked")

        import asyncio
        asyncio.create_task(_send_confirmation_email(db, payment, order_id))

    elif event_type == "PAYMENT_FAILED_WEBHOOK" or payment_status in ("FAILED", "USER_DROPPED"):
        logger.info(f"Processing FAILED for order {order_id}, reason={payment_data.get('payment_message')}")
        payment.cf_payment_id = cf_payment_id
        payment.status = "failed"
        payment.failed_at = _now()
        payment.error_code = payment_data.get("payment_message")
        payment.error_description = payment_data.get("payment_message")
        payment.payment_method = payment_data.get("payment_group")
        payment.contact = payment_data.get("customer_details", {}).get("customer_phone")
        payment.email = payment_data.get("customer_details", {}).get("customer_email")
        db.commit()
        logger.info(f"Payment {order_id} marked failed")

    elif event_type == "PAYMENT_USER_DROPPED_WEBHOOK":
        logger.info(f"Processing USER_DROPPED for order {order_id}")
        payment.status = "failed"
        payment.failed_at = _now()
        payment.error_description = "User dropped payment"
        db.commit()
        logger.info(f"Payment {order_id} marked failed (user dropped)")

    else:
        logger.info(f"Unhandled Cashfree webhook event: {event_type} / status: {payment_status}")

    logger.info(f"Webhook processing complete for order {order_id}")
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
# GET /payment/verify/{order_id}  — frontend polls this after SDK returns
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/verify/{order_id}")
async def verify_payment(
    order_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Poll Cashfree for the latest order status and sync it to our DB.
    Call this after the JS SDK returns — acts as a fallback when webhook is delayed/missed (e.g. localhost dev).
    """
    payment = db.query(Payment).filter(
        Payment.cf_order_id == order_id,
        Payment.user_id == current_user.id,
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Order not found")

    # Already confirmed — no need to call Cashfree
    if payment.status == "paid":
        logger.info(f"verify/{order_id}: already paid, returning early")
        return {"status": "paid", "order_id": order_id}

    logger.info(f"verify/{order_id}: querying Cashfree for order status")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Get order-level status
            order_resp = await client.get(
                f"{_cashfree_base_url()}/orders/{order_id}",
                headers=_cashfree_headers(),
            )
            order_resp.raise_for_status()
            order_data = order_resp.json()

            # Get payments under this order
            pay_resp = await client.get(
                f"{_cashfree_base_url()}/orders/{order_id}/payments",
                headers=_cashfree_headers(),
            )
            pay_resp.raise_for_status()
            payments_list = pay_resp.json()  # list of payment objects
    except Exception as e:
        logger.error(f"verify/{order_id}: Cashfree API error: {e}")
        raise HTTPException(status_code=502, detail="Could not reach Cashfree. Try again.")

    logger.info(f"verify/{order_id}: Cashfree order_status={order_data.get('order_status')} payments={len(payments_list)}")

    # Find the successful payment if any
    success_pay = next((p for p in payments_list if p.get("payment_status") == "SUCCESS"), None)
    failed_pay  = next((p for p in payments_list if p.get("payment_status") in ("FAILED", "USER_DROPPED")), None)

    if success_pay:
        if payment.status != "paid":
            card_info = _extract_card_info(success_pay)
            payment.cf_payment_id = str(success_pay.get("cf_payment_id", "")) or None
            payment.status = "paid"
            payment.paid_at = _now()
            payment.payment_method = success_pay.get("payment_group")
            payment.bank = success_pay.get("bank_reference")
            payment.vpa = (success_pay.get("payment_method", {}) or {}).get("upi", {}).get("upi_id")
            payment.card_network = card_info["card_network"]
            payment.card_issuer = card_info["card_issuer"]
            payment.card_last4 = card_info["card_last4"]
            payment.international = card_info["international"]
            payment.contact = success_pay.get("customer_details", {}).get("customer_phone")
            payment.email = success_pay.get("customer_details", {}).get("customer_email")
            payment.amount_paid = success_pay.get("payment_amount")
            _unlock_enrollment(db, payment)
            db.commit()
            logger.info(f"verify/{order_id}: marked paid via verify endpoint")
            asyncio.create_task(_send_confirmation_email(db, payment, order_id))
        return {"status": "paid", "order_id": order_id}

    elif failed_pay:
        if payment.status != "failed":
            payment.status = "failed"
            payment.failed_at = _now()
            payment.cf_payment_id = str(failed_pay.get("cf_payment_id", "")) or None
            payment.error_description = failed_pay.get("payment_message")
            payment.payment_method = failed_pay.get("payment_group")
            db.commit()
            logger.info(f"verify/{order_id}: marked failed via verify endpoint")
        return {"status": "failed", "order_id": order_id}

    # Payment still pending (user hasn't completed yet)
    return {"status": payment.status, "order_id": order_id}


# ─────────────────────────────────────────────────────────────────────────────
# GET /payment/history
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/history", response_model=list[PaymentOut])
def get_payment_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get payment history for the current user."""
    return (
        db.query(Payment)
        .filter(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .all()
    )
