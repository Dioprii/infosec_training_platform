"""Настройки читаются из переменных окружения (см. .env.example)."""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _flag(name, default="0"):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


class Config:
    DB_PATH = os.environ.get("ACADEMY_DB", str(ROOT / "data" / "academy.db"))
    CONTENT_PATH = os.environ.get("ACADEMY_CONTENT", str(ROOT / "backend" / "content" / "course.json"))
    FRONTEND_DIR = str(ROOT / "frontend")
    COOKIE_NAME = "sk_session"
    COOKIE_SECURE = _flag("COOKIE_SECURE")              # включите за HTTPS
    SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "30"))
    TRUST_PROXY = _flag("TRUST_PROXY")                  # за nginx/traefik: читать X-Forwarded-*
    ALLOW_ORG_SIGNUP = _flag("ALLOW_ORG_SIGNUP", "1")   # публичное создание компаний
    ALLOW_INDIVIDUAL_SIGNUP = _flag("ALLOW_INDIVIDUAL_SIGNUP", "1")
    REVIEW_DELAY_HOURS = int(os.environ.get("REVIEW_DELAY_HOURS", "48"))
    EXAM_QUESTIONS_PER_MODULE = 2
    EXAM_PASS_SHARE = 0.8
    MIN_GROUP = int(os.environ.get("MIN_GROUP", "3"))   # k-анонимность статистики ошибок
    MAX_CONTENT_LENGTH = 64 * 1024
