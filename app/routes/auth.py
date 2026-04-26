import random
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, verify_refresh_token,
)
from app.models.user import User
from app.models.otp import PendingUser, PasswordResetOTP
from app.schemas.auth import (
    UserCreate, UserLogin, Token, RefreshRequest, OTPVerify,
    ForgotPasswordRequest, ResetPassword,
)
from app.utils.mail import send_otp_email, send_password_reset_email

logger = logging.getLogger(__name__)
router = APIRouter()

OTP_EXPIRY_MINUTES = 10


def _make_tokens(user_id: str) -> dict:
    data = {"sub": str(user_id)}
    return {
        "access_token":  create_access_token(data),
        "refresh_token": create_refresh_token(data),
        "token_type":    "bearer",
    }


def _generate_otp() -> str:
    return str(random.randint(100000, 999999))


# ── Step 1: Register → send OTP ──────────────────────────────────────────────

@router.post("/register")
async def register(payload: UserCreate, db: Session = Depends(get_db)):
    """
    Accepts registration details, sends a 6-digit OTP to the email.
    Does NOT create the user yet — call /verify-otp to complete registration.
    """
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    otp        = _generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)

    # Upsert pending record (re-registration attempt resets OTP)
    pending = db.query(PendingUser).filter(PendingUser.email == payload.email).first()
    if pending:
        pending.hashed_password = hash_password(payload.password)
        pending.full_name       = payload.full_name
        pending.otp             = otp
        pending.expires_at      = expires_at
    else:
        pending = PendingUser(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            otp=otp,
            expires_at=expires_at,
        )
        db.add(pending)

    db.commit()

    try:
        await send_otp_email(payload.email, otp)
    except Exception as e:
        logger.error(f"Failed to send OTP email to {payload.email}: {e}")
        raise HTTPException(status_code=503, detail="Failed to send OTP email. Try again.")

    return {"message": f"OTP sent to {payload.email}. Valid for {OTP_EXPIRY_MINUTES} minutes."}


# ── Step 2: Verify OTP → create user, return tokens ──────────────────────────

@router.post("/verify-otp", response_model=Token)
def verify_otp(payload: OTPVerify, db: Session = Depends(get_db)):
    """
    Verifies the OTP. On success, creates the user and returns access + refresh tokens.
    """
    pending = db.query(PendingUser).filter(PendingUser.email == payload.email).first()

    if not pending:
        raise HTTPException(status_code=404, detail="No pending registration for this email")

    if datetime.now(timezone.utc) > pending.expires_at:
        db.delete(pending)
        db.commit()
        raise HTTPException(status_code=410, detail="OTP expired. Please register again.")

    if pending.otp != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Create verified user
    user = User(
        email=pending.email,
        hashed_password=pending.hashed_password,
        full_name=pending.full_name,
    )
    db.add(user)
    db.delete(pending)
    db.commit()
    db.refresh(user)

    return _make_tokens(user.id)


# ── Login (JSON) ──────────────────────────────────────────────────────────────

@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return _make_tokens(user.id)


# ── Login (Swagger OAuth2 form) ───────────────────────────────────────────────

@router.post("/login/swagger", response_model=Token, include_in_schema=False)
def login_swagger(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Form-based login used by Swagger UI authorize dialog."""
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return _make_tokens(user.id)


# ── Refresh ───────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    user_id = verify_refresh_token(payload.refresh_token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"Refresh attempted for non-existent user_id={user_id}")
        raise HTTPException(status_code=401, detail="User not found")
    return _make_tokens(user.id)


# ── Forgot Password ───────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Send a password-reset OTP to the given email (silent if user not found)."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered")

    otp        = _generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)

    record = db.query(PasswordResetOTP).filter(PasswordResetOTP.email == payload.email).first()
    if record:
        record.otp        = otp
        record.expires_at = expires_at
    else:
        record = PasswordResetOTP(email=payload.email, otp=otp, expires_at=expires_at)
        db.add(record)

    db.commit()

    try:
        await send_password_reset_email(payload.email, otp)
    except Exception as e:
        logger.error(f"Failed to send reset OTP to {payload.email}: {e}")
        raise HTTPException(status_code=503, detail="Failed to send OTP email. Try again.")

    return {"message": "OTP has been sent to your email."}


# ── Reset Password ────────────────────────────────────────────────────────────

@router.post("/reset-password")
def reset_password(payload: ResetPassword, db: Session = Depends(get_db)):
    """Verify OTP and set the new password in one step."""
    record = db.query(PasswordResetOTP).filter(PasswordResetOTP.email == payload.email).first()
    if not record:
        raise HTTPException(status_code=404, detail="Email not registered or no OTP requested")
    if record.otp != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if datetime.now(timezone.utc) > record.expires_at:
        db.delete(record)
        db.commit()
        raise HTTPException(status_code=410, detail="OTP expired. Request a new one.")

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(payload.new_password)
    db.delete(record)
    db.commit()

    return {"message": "Password reset successfully. You can now log in."}
