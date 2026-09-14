"""
Configuration for the SPARTA Space Threat Modeling Platform.

Security notes:
- SECRET_KEY is read from the environment. There is no hardcoded fallback
  secret in this file. In development, run `python run.py` once and it will
  generate and print a random key to export for the session; in production
  you must set SPARTA_SECRET_KEY yourself (e.g. via your secrets manager).
- SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE are set defensively. Turn
  SESSION_COOKIE_SECURE off only for plain-HTTP local development.
- SQLALCHEMY_DATABASE_URI defaults to a local SQLite file; all queries in
  this codebase go through the SQLAlchemy ORM (no hand-built SQL strings),
  which is what protects against SQL injection here.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SPARTA_SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "SPARTA_DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'sparta_platform.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SPARTA_HTTPS", "1") == "1"

    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2MB - generous for form/JSON payloads, denies large-body abuse

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Optional: enables the AI-assisted narrative step in app/ai_assist.py.
    # The engine works fully without this - it is an enhancement, not a dependency.
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

    DATA_DIR = BASE_DIR / "app" / "data"


class DevConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProdConfig(Config):
    DEBUG = False
