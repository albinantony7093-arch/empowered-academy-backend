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
    REFRESH_TOKEN_EXPIRE_MINUTES:  int = 10
    OPENAI_API_KEY:              str  = ""
    ALLOWED_ORIGINS: List[str]       = ["*"]

    # Mail
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM:     str = ""
    MAIL_SERVER:   str = "smtp.gmail.com"
    MAIL_PORT:     int = 587

    # Frontend
    FRONTEND_URL: str = "https://empowered-82b6d.web.app/"

    # Razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

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
