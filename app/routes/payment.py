from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import razorpay
import hmac
import hashlib
import logging

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.payment import Payment
from app.models.course import Course, Enrollment
from app.schemas.payment import (
    CreatePaymentOrderRequest,
    CreatePaymentOrderResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
    PaymentOut
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@router.post("/create-order", response_model=CreatePaymentOrderResponse)
def create_payment_order(
    payload: CreatePaymentOrderRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Create a Razorpay order for course payment.
    User must be enrolled with 'locked' status (trial expired).
    """
    # Check if course exists
    course = db.query(Course).filter(
        Course.id == payload.course_id,
        Course.is_active == True
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Check enrollment status
    enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == current_user.id,
        Enrollment.course_id == payload.course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=403,
            detail="You must enroll in the course first to make a payment"
        )
    
    # Only allow payment if status is 'locked' (trial expired)
    if enrollment.payment_status == "paid":
        raise HTTPException(
            status_code=409,
            detail="You have already paid for this course"
        )
    
    if enrollment.payment_status not in ["locked", "trial"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot process payment for enrollment with status: {enrollment.payment_status}"
        )
    
    # Check if there's already a pending payment
    existing_payment = db.query(Payment).filter(
        Payment.enrollment_id == enrollment.id,
        Payment.status == "created"
    ).first()
    
    if existing_payment:
        # Return existing order
        return CreatePaymentOrderResponse(
            order_id=existing_payment.razorpay_order_id,
            amount=float(existing_payment.amount),
            currency=existing_payment.currency,
            razorpay_key_id=settings.RAZORPAY_KEY_ID
        )
    
    # Create Razorpay order
    amount_in_paise = int(float(course.price) * 100)  # Convert to paise
    
    try:
        # Create short receipt (max 40 chars) - use first 8 chars of IDs
        receipt = f"c{course.id[:8]}_u{current_user.id[:8]}"
        
        razorpay_order = razorpay_client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": {
                "course_id": course.id,
                "course_title": course.title,
                "user_id": current_user.id,
                "enrollment_id": enrollment.id
            }
        })
    except Exception as e:
        logger.error(f"Failed to create Razorpay order: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create payment order. Please try again later."
        )
    
    # Save payment record
    payment = Payment(
        user_id=current_user.id,
        course_id=course.id,
        enrollment_id=enrollment.id,
        razorpay_order_id=razorpay_order["id"],
        amount=course.price,
        currency="INR",
        status="created"
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
    """
    Verify Razorpay payment signature and update enrollment status to 'paid'.
    """
    # Find payment record
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
    
    # Verify signature
    generated_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    if generated_signature != payload.razorpay_signature:
        payment.status = "failed"
        payment.error_description = "Invalid payment signature"
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    
    # Update payment record
    payment.razorpay_payment_id = payload.razorpay_payment_id
    payment.razorpay_signature = payload.razorpay_signature
    payment.status = "paid"
    
    # Update enrollment status
    enrollment = db.query(Enrollment).filter(
        Enrollment.id == payment.enrollment_id
    ).first()
    
    if enrollment:
        enrollment.payment_status = "paid"
    
    db.commit()
    
    logger.info(f"Payment verified successfully for order {payload.razorpay_order_id}")
    
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
    """
    Handle Razorpay webhook events.
    Verify webhook signature and process payment events.
    """
    # Get webhook signature from headers
    webhook_signature = request.headers.get("X-Razorpay-Signature")
    
    if not webhook_signature:
        raise HTTPException(status_code=400, detail="Missing webhook signature")
    
    # Get request body
    body = await request.body()
    
    # Verify webhook signature
    try:
        razorpay_client.utility.verify_webhook_signature(
            body.decode(),
            webhook_signature,
            settings.RAZORPAY_WEBHOOK_SECRET
        )
    except razorpay.errors.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    
    # Parse webhook data
    import json
    webhook_data = json.loads(body.decode())
    
    event = webhook_data.get("event")
    payload_data = webhook_data.get("payload", {}).get("payment", {}).get("entity", {})
    
    logger.info(f"Received webhook event: {event}")
    
    # Handle payment.captured event
    if event == "payment.captured":
        order_id = payload_data.get("order_id")
        payment_id = payload_data.get("id")
        
        payment = db.query(Payment).filter(
            Payment.razorpay_order_id == order_id
        ).first()
        
        if payment and payment.status == "created":
            payment.razorpay_payment_id = payment_id
            payment.status = "paid"
            payment.payment_method = payload_data.get("method")
            
            # Update enrollment
            enrollment = db.query(Enrollment).filter(
                Enrollment.id == payment.enrollment_id
            ).first()
            
            if enrollment:
                enrollment.payment_status = "paid"
            
            db.commit()
            logger.info(f"Payment {payment_id} marked as paid via webhook")
    
    # Handle payment.failed event
    elif event == "payment.failed":
        order_id = payload_data.get("order_id")
        payment_id = payload_data.get("id")
        error_description = payload_data.get("error_description", "Payment failed")
        
        payment = db.query(Payment).filter(
            Payment.razorpay_order_id == order_id
        ).first()
        
        if payment:
            payment.razorpay_payment_id = payment_id
            payment.status = "failed"
            payment.error_description = error_description
            db.commit()
            logger.info(f"Payment {payment_id} marked as failed via webhook")
    
    # Handle payment.dispute.created event
    elif event == "payment.dispute.created":
        payment_id = payload_data.get("id")
        dispute_id = webhook_data.get("payload", {}).get("dispute", {}).get("entity", {}).get("id")
        dispute_amount = webhook_data.get("payload", {}).get("dispute", {}).get("entity", {}).get("amount", 0)
        dispute_reason = webhook_data.get("payload", {}).get("dispute", {}).get("entity", {}).get("reason_description", "Dispute raised")
        
        payment = db.query(Payment).filter(
            Payment.razorpay_payment_id == payment_id
        ).first()
        
        if payment:
            # Mark payment as disputed
            payment.status = "disputed"
            payment.error_description = f"Dispute created: {dispute_reason} (Dispute ID: {dispute_id})"
            
            # Lock enrollment until dispute is resolved
            enrollment = db.query(Enrollment).filter(
                Enrollment.id == payment.enrollment_id
            ).first()
            
            if enrollment and enrollment.payment_status == "paid":
                enrollment.payment_status = "locked"
            
            db.commit()
            logger.warning(f"Dispute created for payment {payment_id}: {dispute_reason}")
    
    # Handle payment.dispute.action_required event
    elif event == "payment.dispute.action_required":
        payment_id = payload_data.get("id")
        dispute_id = webhook_data.get("payload", {}).get("dispute", {}).get("entity", {}).get("id")
        
        payment = db.query(Payment).filter(
            Payment.razorpay_payment_id == payment_id
        ).first()
        
        if payment:
            payment.error_description = f"Dispute action required (Dispute ID: {dispute_id})"
            db.commit()
            logger.warning(f"Action required for dispute on payment {payment_id}")
    
    # Handle payment.dispute.won event
    elif event == "payment.dispute.won":
        payment_id = payload_data.get("id")
        dispute_id = webhook_data.get("payload", {}).get("dispute", {}).get("entity", {}).get("id")
        
        payment = db.query(Payment).filter(
            Payment.razorpay_payment_id == payment_id
        ).first()
        
        if payment:
            # Restore payment to paid status
            payment.status = "paid"
            payment.error_description = f"Dispute won (Dispute ID: {dispute_id})"
            
            # Restore enrollment access
            enrollment = db.query(Enrollment).filter(
                Enrollment.id == payment.enrollment_id
            ).first()
            
            if enrollment:
                enrollment.payment_status = "paid"
            
            db.commit()
            logger.info(f"Dispute won for payment {payment_id}, access restored")
    
    # Handle payment.dispute.lost event
    elif event == "payment.dispute.lost":
        payment_id = payload_data.get("id")
        dispute_id = webhook_data.get("payload", {}).get("dispute", {}).get("entity", {}).get("id")
        
        payment = db.query(Payment).filter(
            Payment.razorpay_payment_id == payment_id
        ).first()
        
        if payment:
            # Mark payment as refunded (money returned to customer)
            payment.status = "refunded"
            payment.error_description = f"Dispute lost (Dispute ID: {dispute_id})"
            
            # Lock enrollment permanently
            enrollment = db.query(Enrollment).filter(
                Enrollment.id == payment.enrollment_id
            ).first()
            
            if enrollment:
                enrollment.payment_status = "cancelled"
            
            db.commit()
            logger.warning(f"Dispute lost for payment {payment_id}, enrollment cancelled")
    
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
