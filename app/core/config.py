from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    DATABASE_URL:                str
    SECRET_KEY:                  str
    ALGORITHM:                   str  = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int  = 60 * 24
    OPENAI_API_KEY:              str
    ALLOWED_ORIGINS: List[str]       = ["https://ai.empoweredacademy.in"]


def _validate_env(s: Settings) -> None:
    """Fail fast at startup if critical env vars are missing or placeholder."""
    missing = []
    if not s.DATABASE_URL:
        missing.append("DATABASE_URL")
    if not s.SECRET_KEY or s.SECRET_KEY in ("your-super-secret-key-change-in-production", "secret"):
        missing.append("SECRET_KEY (must not be a placeholder value)")
    if not s.OPENAI_API_KEY or s.OPENAI_API_KEY.startswith("sk-your"):
        missing.append("OPENAI_API_KEY")
    if missing:
        raise EnvironmentError(
            f"Missing or invalid environment variables: {', '.join(missing)}. "
            "Check your .env file."
        )


settings = Settings()
_validate_env(settings)
