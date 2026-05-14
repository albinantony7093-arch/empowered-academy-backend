from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Brand constants
# ──────────────────────────────────────────────
BRAND_NAME     = "Empowered Academy"
BRAND_COLOR    = "#C0392B"
BRAND_DARK     = "#1a1a2e"
SUPPORT_PHONE  = "9152987821"
SUPPORT_EMAIL  = "support@empoweredacademy.in"
REFUND_EMAIL   = "refunds@empoweredacademy.in"
POWERED_BY     = "Powered by Red Cross Academy, Kottayam, Kerala"

# ──────────────────────────────────────────────
# Mail config
# ──────────────────────────────────────────────
def _get_mail_config() -> ConnectionConfig | None:
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

# ──────────────────────────────────────────────
# Base HTML layout
# ──────────────────────────────────────────────
def _base_template(title: str, content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f4;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:30px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">

      <!-- HEADER -->
      <tr><td style="background:{BRAND_DARK};padding:28px 40px;text-align:center;">
        <div style="display:inline-block;background:{BRAND_COLOR};border-radius:50%;width:52px;height:52px;
                    line-height:52px;text-align:center;font-size:26px;color:#fff;font-weight:bold;margin-bottom:10px;">E</div>
        <h1 style="color:#ffffff;font-size:22px;margin:6px 0 4px;letter-spacing:1px;">{BRAND_NAME}</h1>
        <p style="color:#aaaaaa;font-size:12px;margin:0;">Performance &middot; Mind &middot; Rank &mdash; NEET UG &amp; PG</p>
      </td></tr>

      <!-- BODY -->
      <tr><td style="padding:36px 40px;color:#333333;font-size:15px;line-height:1.7;">{content}</td></tr>

      <!-- FOOTER -->
      <tr><td style="background:#f9f9f9;padding:20px 40px;text-align:center;border-top:1px solid #eeeeee;">
        <p style="font-size:12px;color:#888;margin:0 0 4px;">
          Need help? Call us at
          <a href="tel:{SUPPORT_PHONE}" style="color:{BRAND_COLOR};text-decoration:none;font-weight:bold;"> {SUPPORT_PHONE}</a>
          &nbsp;|&nbsp;
          <a href="mailto:{SUPPORT_EMAIL}" style="color:{BRAND_COLOR};text-decoration:none;">{SUPPORT_EMAIL}</a>
        </p>
        <p style="font-size:11px;color:#aaa;margin:4px 0 0;">{POWERED_BY}</p>
        <p style="font-size:11px;color:#aaa;margin:4px 0 0;">&copy; 2025 {BRAND_NAME} &middot; Red Cross Academy, Kottayam</p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""

# ──────────────────────────────────────────────
# Refund info block (reused in payment emails)
# ──────────────────────────────────────────────
def _refund_block() -> str:
    return f"""
<div style="background:#fff8f8;border:1px solid #f5c6c6;border-radius:6px;padding:18px 20px;margin:24px 0;">
  <p style="margin:0 0 8px;font-size:13px;font-weight:bold;color:{BRAND_DARK};">&#128196; Refund &amp; Cancellation Policy</p>
  <p style="margin:0 0 8px;font-size:13px;color:#555;">
    If you face any payment issues or wish to request a refund, please contact us within <strong>7 days</strong> of your transaction.
  </p>
  <table width="100%" cellpadding="0" cellspacing="0" style="font-size:13px;color:#555;">
    <tr>
      <td style="padding:4px 0;width:130px;">&#128231; Email us at</td>
      <td><a href="mailto:{REFUND_EMAIL}" style="color:{BRAND_COLOR};font-weight:bold;">{REFUND_EMAIL}</a></td>
    </tr>
    <tr>
      <td style="padding:4px 0;">&#128222; Call / WhatsApp</td>
      <td><a href="tel:{SUPPORT_PHONE}" style="color:{BRAND_COLOR};font-weight:bold;">{SUPPORT_PHONE}</a></td>
    </tr>
  </table>
  <p style="margin:10px 0 0;font-size:12px;color:#888;">
    Please keep your <strong>Transaction ID</strong> and <strong>registered email</strong> handy when reaching out.
    Refunds are processed within 5&ndash;7 business days after verification.
  </p>
</div>"""

# ──────────────────────────────────────────────
# OTP Template
# ──────────────────────────────────────────────
def _otp_template(otp: str, purpose: str, expiry_minutes: int = 10) -> str:
    content = f"""
<h2 style="color:{BRAND_DARK};margin-top:0;font-size:22px;">Verification Code</h2>
<p>Hello,</p>
<p>We received a request to <strong>{purpose}</strong> on your {BRAND_NAME} account.
Use the one-time password below to proceed:</p>

<div style="background:#f9f9f9;border:2px dashed {BRAND_COLOR};border-radius:8px;
            text-align:center;padding:28px;margin:28px 0;">
  <p style="margin:0 0 8px;font-size:12px;color:#888;text-transform:uppercase;letter-spacing:2px;">Your One-Time Password</p>
  <div style="font-size:46px;font-weight:bold;color:{BRAND_COLOR};letter-spacing:12px;">{otp}</div>
  <p style="margin:14px 0 0;font-size:13px;color:#888;">&#8987; Expires in <strong>{expiry_minutes} minutes</strong></p>
</div>

<p style="font-size:14px;color:#555;">For your security, <strong>do not share this OTP</strong> with anyone &mdash;
including {BRAND_NAME} support staff.</p>

<hr style="border:none;border-top:1px solid #eeeeee;margin:24px 0;"/>
<p style="font-size:13px;color:#999;">If you did not request this, you can safely ignore this email. Your account remains secure.</p>"""
    return _base_template(f"Your OTP — {BRAND_NAME}", content)

# ──────────────────────────────────────────────
# Enrollment Confirmation Template
# ──────────────────────────────────────────────
def _enrollment_template(
    full_name: str,
    course_title: str,
    course_id: str = "",
    transaction_date: str = "",
    transaction_id: str = "",
    razorpay_payment_id: str = "",
) -> str:
    tx_rows = ""
    if transaction_date:
        tx_rows += f"""
    <tr>
      <td style="padding:10px 14px;border-bottom:1px solid #eee;color:#555;font-size:14px;">Transaction Date</td>
      <td style="padding:10px 14px;border-bottom:1px solid #eee;font-weight:bold;font-size:14px;">{transaction_date}</td>
    </tr>"""
    if transaction_id:
        tx_rows += f"""
    <tr>
      <td style="padding:10px 14px;border-bottom:1px solid #eee;color:#555;font-size:14px;">Order ID</td>
      <td style="padding:10px 14px;border-bottom:1px solid #eee;font-size:13px;color:#666;">{transaction_id}</td>
    </tr>"""
    if razorpay_payment_id:
        tx_rows += f"""
    <tr>
      <td style="padding:10px 14px;border-bottom:1px solid #eee;color:#555;font-size:14px;">Payment ID</td>
      <td style="padding:10px 14px;border-bottom:1px solid #eee;font-size:13px;color:#666;">{razorpay_payment_id}</td>
    </tr>"""

    course_url = f"{settings.FRONTEND_URL}/courses/{course_id}" if course_id else f"{settings.FRONTEND_URL}/courses"

    content = f"""
<h2 style="color:{BRAND_DARK};margin-top:0;font-size:22px;">&#127881; Enrollment Confirmed!</h2>
<p>Hi <strong>{full_name}</strong>,</p>
<p>Your payment was successful. You are now enrolled in:</p>

<div style="background:#f9f9f9;border-left:4px solid {BRAND_COLOR};border-radius:4px;padding:18px 20px;margin:20px 0;">
  <p style="margin:0;font-size:12px;color:#888;text-transform:uppercase;letter-spacing:1px;">Course Enrolled</p>
  <p style="margin:6px 0 0;font-size:18px;font-weight:bold;color:{BRAND_DARK};">{course_title}</p>
</div>

<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #eeeeee;border-radius:6px;margin:20px 0;">
  <tr style="background:#f0f0f0;">
    <th style="text-align:left;padding:10px 14px;font-size:13px;color:#555;border-bottom:2px solid #ddd;">Detail</th>
    <th style="text-align:left;padding:10px 14px;font-size:13px;color:#555;border-bottom:2px solid #ddd;">Info</th>
  </tr>
  <tr>
    <td style="padding:10px 14px;border-bottom:1px solid #eee;color:#555;font-size:14px;">Course</td>
    <td style="padding:10px 14px;border-bottom:1px solid #eee;font-weight:bold;font-size:14px;">{course_title}</td>
  </tr>
  <tr>
    <td style="padding:10px 14px;border-bottom:1px solid #eee;color:#555;font-size:14px;">Sold by</td>
    <td style="padding:10px 14px;border-bottom:1px solid #eee;font-size:14px;">{BRAND_NAME}</td>
  </tr>
  {tx_rows}
</table>

<p>You can access your course anytime by logging into your <strong>{BRAND_NAME}</strong> account.</p>

<div style="text-align:center;margin:28px 0;">
  <a href="{course_url}" style="background:{BRAND_COLOR};color:#ffffff;padding:14px 32px;border-radius:6px;
                     text-decoration:none;font-weight:bold;font-size:15px;display:inline-block;">
    Start Learning &#8594;
  </a>
</div>

{_refund_block()}

<hr style="border:none;border-top:1px solid #eeeeee;margin:24px 0;"/>
<p style="font-size:13px;color:#999;">If you have questions about your enrollment, please contact our support team.</p>"""
    return _base_template(f"Enrollment Confirmed — {course_title}", content)

# ──────────────────────────────────────────────
# Trial Enrollment Template
# ──────────────────────────────────────────────
def _trial_template(full_name: str, course_title: str, course_id: str, trial_ends_at: str) -> str:
    course_url = f"{settings.FRONTEND_URL}/courses/{course_id}" if course_id else f"{settings.FRONTEND_URL}/courses"
    content = f"""
<h2 style="color:{BRAND_DARK};margin-top:0;font-size:22px;">&#128640; Your Free Trial Has Started!</h2>
<p>Hi <strong>{full_name}</strong>,</p>
<p>You've been granted a <strong>4-day free trial</strong> for:</p>

<div style="background:#f9f9f9;border-left:4px solid {BRAND_COLOR};border-radius:4px;padding:18px 20px;margin:20px 0;">
  <p style="margin:0;font-size:12px;color:#888;text-transform:uppercase;letter-spacing:1px;">Trial Course</p>
  <p style="margin:6px 0 0;font-size:18px;font-weight:bold;color:{BRAND_DARK};">{course_title}</p>
</div>

<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #eeeeee;border-radius:6px;margin:20px 0;">
  <tr style="background:#f0f0f0;">
    <th style="text-align:left;padding:10px 14px;font-size:13px;color:#555;border-bottom:2px solid #ddd;">Detail</th>
    <th style="text-align:left;padding:10px 14px;font-size:13px;color:#555;border-bottom:2px solid #ddd;">Info</th>
  </tr>
  <tr>
    <td style="padding:10px 14px;border-bottom:1px solid #eee;color:#555;font-size:14px;">Trial Type</td>
    <td style="padding:10px 14px;border-bottom:1px solid #eee;font-weight:bold;font-size:14px;">4-Day Free Access</td>
  </tr>
  <tr>
    <td style="padding:10px 14px;color:#555;font-size:14px;">Trial Ends On</td>
    <td style="padding:10px 14px;font-weight:bold;font-size:14px;color:{BRAND_COLOR};">{trial_ends_at}</td>
  </tr>
</table>

<p>After your trial ends, complete your purchase to continue accessing the full course content.</p>

<div style="text-align:center;margin:28px 0;">
  <a href="{course_url}" style="background:{BRAND_COLOR};color:#ffffff;padding:14px 32px;border-radius:6px;
                     text-decoration:none;font-weight:bold;font-size:15px;display:inline-block;">
    Start Learning &#8594;
  </a>
</div>

<hr style="border:none;border-top:1px solid #eeeeee;margin:24px 0;"/>
<p style="font-size:13px;color:#999;">Make the most of your trial &mdash; dive in and start exploring today!</p>"""
    return _base_template(f"Your Free Trial — {course_title}", content)

# ──────────────────────────────────────────────
# Payment Failed Template
# ──────────────────────────────────────────────
def _payment_failed_template(full_name: str, course_title: str, transaction_id: str = "") -> str:
    tx_row = ""
    if transaction_id:
        tx_row = f"""
    <tr>
      <td style="padding:10px 14px;border-bottom:1px solid #eee;color:#555;font-size:14px;">Transaction ID</td>
      <td style="padding:10px 14px;border-bottom:1px solid #eee;font-size:13px;color:#666;">{transaction_id}</td>
    </tr>"""

    content = f"""
<h2 style="color:{BRAND_DARK};margin-top:0;font-size:22px;">&#9888;&#65039; Payment Issue Detected</h2>
<p>Hi <strong>{full_name}</strong>,</p>
<p>We noticed a problem with your recent payment for:</p>

<div style="background:#fff8f8;border-left:4px solid {BRAND_COLOR};border-radius:4px;padding:18px 20px;margin:20px 0;">
  <p style="margin:0;font-size:12px;color:#888;text-transform:uppercase;letter-spacing:1px;">Course</p>
  <p style="margin:6px 0 0;font-size:18px;font-weight:bold;color:{BRAND_DARK};">{course_title}</p>
</div>

<p style="font-size:14px;color:#555;">
  If your account was debited but enrollment was not activated, <strong>please do not worry</strong> —
  your money is safe and will be refunded automatically within 5&ndash;7 business days.
  You can also reach us directly for faster resolution.
</p>

{_refund_block()}

<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #eeeeee;border-radius:6px;margin:20px 0;">
  <tr style="background:#f0f0f0;">
    <th style="text-align:left;padding:10px 14px;font-size:13px;color:#555;border-bottom:2px solid #ddd;">Detail</th>
    <th style="text-align:left;padding:10px 14px;font-size:13px;color:#555;border-bottom:2px solid #ddd;">Info</th>
  </tr>
  <tr>
    <td style="padding:10px 14px;border-bottom:1px solid #eee;color:#555;font-size:14px;">Course</td>
    <td style="padding:10px 14px;border-bottom:1px solid #eee;font-weight:bold;font-size:14px;">{course_title}</td>
  </tr>
  {tx_row}
</table>

<hr style="border:none;border-top:1px solid #eeeeee;margin:24px 0;"/>
<p style="font-size:13px;color:#999;">We apologise for the inconvenience. Our team is here to help you.</p>"""
    return _base_template(f"Payment Issue — {BRAND_NAME}", content)

# ──────────────────────────────────────────────
# Core send helper
# ──────────────────────────────────────────────
async def _send_email(email: str, subject: str, html_body: str) -> None:
    conf = _get_mail_config()
    if conf is None:
        logger.warning("Mail not configured — email not sent to %s", email)
        raise RuntimeError(
            "Mail service is not configured. "
            "Set MAIL_USERNAME, MAIL_PASSWORD, and MAIL_FROM in .env"
        )
    message = MessageSchema(
        subject=subject,
        recipients=[email],
        body=html_body,
        subtype=MessageType.html,
    )
    await FastMail(conf).send_message(message)

# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────
async def send_otp_email(email: str, otp: str) -> None:
    html = _otp_template(otp, purpose="verify your account", expiry_minutes=10)
    await _send_email(email, subject=f"[{BRAND_NAME}] Your OTP for Registration", html_body=html)


async def send_password_reset_email(email: str, otp: str) -> None:
    html = _otp_template(otp, purpose="reset your password", expiry_minutes=10)
    await _send_email(email, subject=f"[{BRAND_NAME}] Password Reset OTP", html_body=html)


async def send_enrollment_confirmation_email(
    email: str,
    full_name: str,
    course_title: str,
    course_id: str = "",
    transaction_date: str = "",
    transaction_id: str = "",
    razorpay_payment_id: str = "",
) -> None:
    html = _enrollment_template(full_name, course_title, course_id, transaction_date, transaction_id, razorpay_payment_id)
    await _send_email(email, subject=f"You're enrolled in {course_title} — {BRAND_NAME}", html_body=html)


async def send_trial_enrollment_email(
    email: str,
    full_name: str,
    course_title: str,
    course_id: str = "",
    trial_ends_at: str = "",
) -> None:
    html = _trial_template(full_name, course_title, course_id, trial_ends_at)
    await _send_email(email, subject=f"Your free trial for {course_title} has started — {BRAND_NAME}", html_body=html)


async def send_payment_failed_email(
    email: str,
    full_name: str,
    course_title: str,
    transaction_id: str = "",
) -> None:
    html = _payment_failed_template(full_name, course_title, transaction_id)
    await _send_email(email, subject=f"Payment Issue for {course_title} — {BRAND_NAME}", html_body=html)
