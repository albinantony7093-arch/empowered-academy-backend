from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator
from typing import List
import json


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    DATABASE_URL:                str
    SECRET_KEY:                  str
    ALGORITHM:                   str  = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:   int = 5
    REFRESH_TOKEN_EXPIRE_MINUTES:  int = 4320
    OPENAI_API_KEY:              str  = ""
    ALLOWED_ORIGINS: List[str]       = ["*"]

    # Mail
    MAIL_FROM:     str = "noreply@empoweredacademy.in"

    # Resend
    RESEND_API_KEY: str = ""

    # Frontend
    FRONTEND_URL: str = "https://learn.empoweredacademy.in"

    # Cashfree
    CASHFREE_APP_ID: str = ""
    CASHFREE_SECRET_KEY: str = ""
    CASHFREE_WEBHOOK_SECRET: str = ""
    CASHFREE_ENV: str = "sandbox"  # "sandbox" or "production"

    # Sentry
    SENTRY_DSN: str = ""

    # Crash Course schedule (ISO format, e.g. "2026-06-05T05:00:00+05:30")
    CRASH_COURSE_START: str = "2026-06-05T05:00:00+05:30"
    CRASH_COURSE_END:   str = "2026-06-21T17:00:00+05:30"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            # Single origin as plain string
            return [v.strip()]
        return v


def _validate_env(s: Settings) -> None:
    """Fail fast at startup if critical env vars are missing."""
    missing = []
    if not s.DATABASE_URL:
        missing.append("DATABASE_URL")
    if not s.SECRET_KEY:
        missing.append("SECRET_KEY")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Check your .env file."
        )


settings = Settings()
_validate_env(settings)
