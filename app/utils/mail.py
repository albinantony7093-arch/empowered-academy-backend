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
