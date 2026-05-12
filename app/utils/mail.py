from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def _get_mail_config() -> ConnectionConfig | None:
    """Build ConnectionConfig lazily — returns None if mail is not configured."""
    if not settings.MAIL_USERNAME or settings.MAIL_USERNAME.startswith("your_"):
        return None
    return ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
    )


async def _send_email(email: str, subject: str, body: str) -> None:
    conf = _get_mail_config()
    if conf is None:
        logger.warning("Mail not configured — email not sent")
        raise RuntimeError("Mail service is not configured. Set MAIL_USERNAME, MAIL_PASSWORD, and MAIL_FROM in .env")
    message = MessageSchema(
        subject=subject,
        recipients=[email],
        body=body,
        subtype=MessageType.plain,
    )
    await FastMail(conf).send_message(message)


async def send_otp_email(email: str, otp: str) -> None:
    conf = _get_mail_config()
    if conf is None:
        logger.warning("Mail not configured — OTP email not sent")
        raise RuntimeError("Mail service is not configured. Set MAIL_USERNAME, MAIL_PASSWORD, and MAIL_FROM in .env")

    message = MessageSchema(
        subject="Your Empowered Academy OTP",
        recipients=[email],
        body=f"Your OTP for registration is: {otp}\n\nIt expires in 10 minutes.",
        subtype=MessageType.plain,
    )
    fm = FastMail(conf)
    await fm.send_message(message)


async def send_password_reset_email(email: str, otp: str) -> None:
    await _send_email(
        email,
        subject="Empowered Academy — Password Reset OTP",
        body=f"Your OTP to reset your password is: {otp}\n\nIt expires in 10 minutes.\nIf you did not request this, ignore this email.",
    )


async def send_enrollment_confirmation_email(email: str, full_name: str, course_title: str) -> None:
    name = full_name or "Student"
    await _send_email(
        email,
        subject=f"You're enrolled in {course_title} — Empowered Academy",
        body=(
            f"Hi {name},\n\n"
            f"Your payment was successful and you are now enrolled in:\n\n"
            f"  {course_title}\n\n"
            f"You can access your course anytime by logging into Empowered Academy.\n\n"
            f"If you have any questions, feel free to reach out to our support team.\n\n"
            f"Happy learning!\n"
            f"Team Empowered Academy"
        ),
    )


async def send_trial_enrollment_email(email: str, full_name: str, course_title: str, trial_ends_at: str) -> None:
    name = full_name or "Student"
    await _send_email(
        email,
        subject=f"Your free trial for {course_title} has started — Empowered Academy",
        body=(
            f"Hi {name},\n\n"
            f"You've been enrolled in a 4-day free trial for:\n\n"
            f"  {course_title}\n\n"
            f"Your trial access is valid until {trial_ends_at}.\n\n"
            f"After the trial ends, you'll need to complete your purchase to continue accessing the course.\n\n"
            f"Log in to Empowered Academy to start learning.\n\n"
            f"Happy learning!\n"
            f"Team Empowered Academy"
        ),
    )
