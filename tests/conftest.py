"""
conftest.py — Sets required environment variables before any app module is imported.
This prevents pydantic-settings from failing on missing DATABASE_URL / SECRET_KEY / OPENAI_API_KEY.
"""
import os

os.environ.setdefault("DATABASE_URL",   "sqlite:///./test_run.db")
os.environ.setdefault("SECRET_KEY",     "test-secret-32-chars-not-for-prod-xx")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder-key")
