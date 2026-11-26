"""Аутентификация: пароли, сессии в HttpOnly-cookie, ограничение попыток, защита от CSRF."""
import datetime as dt
import hashlib
import re
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, parse_ts, ts, utcnow


class ApiError(Exception):
    def __init__(self, msg, code=400, field=None):
        super().__init__(msg)
        self.msg, self.code, self.field = msg, code, field


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
COMMON = {"password", "12345678", "123456789", "qwertyui", "qwerty123", "11111111",
          "password1", "iloveyou", "1q2w3e4r", "12341234", "пароль123", "йцукенг1"}


def clean_email(value):
    e = (value or "").strip().lower()
    if not EMAIL_RE.match(e) or len(e) > 120:
        raise ApiError("Проверьте адрес почты", 400, "email")
    return e


def clean_name(value, what="имя"):
    n = re.sub(r"\s+", " ", (value or "").strip())
    if not 1 <= len(n) <= 60:
        raise ApiError(f"Укажите {what} (до 60 символов)", 400, "name")
    return n


def check_password_rules(pw, email=""):
    if not isinstance(pw, str) or len(pw) < 8:
        raise ApiError("Пароль слишком короткий: нужно минимум 8 символов", 400, "password")
    if len(pw) > 128:
        raise ApiError("Пароль слишком длинный", 400, "password")
    if pw.lower() in COMMON or (email and pw.lower() == email.lower()):
        raise ApiError("Этот пароль слишком простой. Лучше длинная фраза из нескольких слов", 400, "password")


def hash_password(pw):
    return generate_password_hash(pw)


def verify_password(h, pw):
    try:
        return check_password_hash(h, pw)
    except Exception:
        return False


# ---------- сессии ----------
def _h(token):
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(db, user_id):
    token = secrets.token_urlsafe(32)
    days = current_app.config["SESSION_DAYS"]
    db.execute("INSERT INTO sessions(token_hash,user_id,created_at,expires_at,ua) VALUES (?,?,?,?,?)",
               (_h(token), user_id, ts(), ts(utcnow() + dt.timedelta(days=days)),
                (request.headers.get("User-Agent") or "")[:200]))
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (ts(),))
    return token


def set_cookie(resp, token):
    c = current_app.config
    resp.set_cookie(c["COOKIE_NAME"], token, max_age=c["SESSION_DAYS"] * 86400, httponly=True,
                    samesite="Lax", secure=c["COOKIE_SECURE"], path="/")


def clear_cookie(resp):
    resp.delete_cookie(current_app.config["COOKIE_NAME"], path="/")


def current_user():
    if "user" in g:
        return g.user
    g.user = None
    token = request.cookies.get(current_app.config["COOKIE_NAME"])
    if token:
        db = get_db()
        row = db.execute("""SELECT u.*, s.expires_at AS s_exp FROM sessions s JOIN users u ON u.id=s.user_id
                            WHERE s.token_hash=?""", (_h(token),)).fetchone()
        if row and row["active"] and row["s_exp"] > ts():
            g.user = row
            g.token = token
    return g.user


def login_required(fn):
    @wraps(fn)
    def w(*a, **kw):
        if not current_user():
            raise ApiError("Нужно войти", 401)
        return fn(*a, **kw)
    return w


def admin_required(fn):
    @wraps(fn)
    @login_required
    def w(*a, **kw):
        u = current_user()
        if u["role"] != "admin" or not u["org_id"]:
            raise ApiError("Недостаточно прав", 403)
        return fn(*a, **kw)
    return w


# ---------- ограничение попыток ----------
def client_ip():
    return request.remote_addr or "?"


def record(db, kind, ok):
    db.execute("INSERT INTO login_attempts(email,ip,ok,ts) VALUES (?,?,?,?)", (kind, client_ip(), int(ok), ts()))


def guard_login(db, email):
    since = ts(utcnow() - dt.timedelta(minutes=15))
    by_mail = db.execute("SELECT COUNT(*) FROM login_attempts WHERE email=? AND ok=0 AND ts>=?", (email, since)).fetchone()[0]
    by_ip = db.execute("SELECT COUNT(*) FROM login_attempts WHERE ip=? AND ok=0 AND ts>=?", (client_ip(), since)).fetchone()[0]
    if by_mail >= 8 or by_ip >= 40:
        raise ApiError("Слишком много неудачных попыток. Подождите 15 минут и попробуйте снова", 429)


def guard_register(db):
    since = ts(utcnow() - dt.timedelta(hours=1))
    n = db.execute("SELECT COUNT(*) FROM login_attempts WHERE email='__register__' AND ip=? AND ts>=?",
                   (client_ip(), since)).fetchone()[0]
    if n >= 20:
        raise ApiError("Слишком много регистраций с этого адреса. Попробуйте позже", 429)


# ---------- защита запросов ----------
def origin_guard():
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.path.startswith("/api/"):
        origin = request.headers.get("Origin")
        if origin and urlparse(origin).netloc != request.host:
            raise ApiError("Запрос отклонён", 403)
        if request.content_length and not request.is_json:
            raise ApiError("Ожидается JSON", 415)


def add_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}
