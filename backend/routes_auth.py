"""Регистрация, вход, профиль."""
import secrets
import datetime as dt

from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import generate_password_hash

from .db import get_db, ts, utcnow
from .security import (ApiError, body, check_password_rules, clean_email, clean_name, client_ip,
                       current_user, clear_cookie, guard_login, guard_register, hash_password,
                       login_required, record, set_cookie, start_session, verify_password)

bp = Blueprint("auth", __name__)
_DUMMY = generate_password_hash("dummy-password-for-timing")
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
DEFAULT_DEPTS = ["Все сотрудники"]


def new_invite_code(db):
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        if not db.execute("SELECT 1 FROM orgs WHERE invite_code=?", (code,)).fetchone():
            return code


def me_payload(db, u):
    org = db.execute("SELECT id,name,gating,allowed_domain FROM orgs WHERE id=?", (u["org_id"],)).fetchone() if u["org_id"] else None
    dept = db.execute("SELECT id,name FROM departments WHERE id=?", (u["dept_id"],)).fetchone() if u["dept_id"] else None
    depts = [dict(r) for r in db.execute("SELECT id,name FROM departments WHERE org_id=? ORDER BY name", (u["org_id"],))] if u["org_id"] else []
    return {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"], "tz": u["tz"], "gender": u["gender"],
            "onboarded": bool(u["onboarded"]), "must_change_password": bool(u["must_change_password"]),
            "org": dict(org) if org else None, "dept": dict(dept) if dept else None, "departments": depts}


def _gender(v):
    return v if v in ("f", "m") else None


def _tz(value):
    from zoneinfo import ZoneInfo
    try:
        ZoneInfo(value)
        return value
    except Exception:
        return "Europe/Moscow"


def _login_response(db, user_id):
    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    db.execute("UPDATE users SET last_login=? WHERE id=?", (ts(), user_id))
    resp = jsonify(user=me_payload(db, row))
    set_cookie(resp, start_session(db, user_id))
    return resp


@bp.get("/session")
def session():
    u = current_user()
    return jsonify(user=me_payload(get_db(), u) if u else None,
                   signup={"individual": current_app.config["ALLOW_INDIVIDUAL_SIGNUP"],
                           "org": current_app.config["ALLOW_ORG_SIGNUP"]})


@bp.get("/orgs/lookup")
def org_lookup():
    db = get_db()
    since = ts(utcnow() - dt.timedelta(minutes=15))
    if db.execute("SELECT COUNT(*) FROM login_attempts WHERE email='__lookup__' AND ip=? AND ok=0 AND ts>=?",
                  (client_ip(), since)).fetchone()[0] >= 30:
        raise ApiError("Слишком много попыток. Подождите немного", 429)
    code = (request.args.get("code") or "").strip().upper()
    org = db.execute("SELECT * FROM orgs WHERE invite_code=?", (code,)).fetchone()
    if not org:
        record(db, "__lookup__", False)
        db.commit()
        raise ApiError("Код компании не найден. Проверьте, что он введён без ошибок", 404, "invite_code")
    depts = [dict(r) for r in db.execute("SELECT id,name FROM departments WHERE org_id=? ORDER BY name", (org["id"],))]
    return jsonify(name=org["name"], departments=depts, allowed_domain=org["allowed_domain"])


@bp.post("/auth/register")
def register():
    db, d, cfg = get_db(), body(), current_app.config
    guard_register(db)
    mode = d.get("mode")
    if mode not in ("individual", "join", "create_org"):
        raise ApiError("Выберите, как вы хотите зарегистрироваться")
    name, email = clean_name(d.get("name")), clean_email(d.get("email"))
    password = d.get("password")
    check_password_rules(password, email)
    if db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        raise ApiError("Эта почта уже зарегистрирована. Войдите в аккаунт", 409, "email")
    org_id = dept_id = None
    role = "learner"
    if mode == "individual":
        if not cfg["ALLOW_INDIVIDUAL_SIGNUP"]:
            raise ApiError("Самостоятельная регистрация отключена. Нужен код компании", 403)
    elif mode == "join":
        org = db.execute("SELECT * FROM orgs WHERE invite_code=?", ((d.get("invite_code") or "").strip().upper(),)).fetchone()
        if not org:
            raise ApiError("Код компании не найден", 404, "invite_code")
        if org["allowed_domain"] and not email.endswith("@" + org["allowed_domain"]):
            raise ApiError(f"Для этой компании нужна рабочая почта @{org['allowed_domain']}", 400, "email")
        org_id = org["id"]
        if d.get("dept_id") not in (None, ""):
            dept = db.execute("SELECT id FROM departments WHERE id=? AND org_id=?", (d.get("dept_id"), org_id)).fetchone()
            if not dept:
                raise ApiError("Выберите подразделение из списка", 400, "dept_id")
            dept_id = dept["id"]
    else:
        if not cfg["ALLOW_ORG_SIGNUP"]:
            raise ApiError("Создание компаний отключено", 403)
        org_name = clean_name(d.get("org_name"), "название компании")
        if len(org_name) < 2:
            raise ApiError("Название компании слишком короткое", 400, "org_name")
        cur = db.execute("INSERT INTO orgs(name,invite_code,created_at) VALUES (?,?,?)",
                         (org_name, new_invite_code(db), ts()))
        org_id, role = cur.lastrowid, "admin"
        raw = d.get("departments") or DEFAULT_DEPTS
        if isinstance(raw, str):
            raw = raw.replace("\n", ",").split(",")
        names = []
        for n in raw if isinstance(raw, list) else DEFAULT_DEPTS:
            n = " ".join(str(n).split())[:60]
            if n and n not in names:
                names.append(n)
        for n in (names[:20] or DEFAULT_DEPTS):
            db.execute("INSERT INTO departments(org_id,name) VALUES (?,?)", (org_id, n))
    cur = db.execute("""INSERT INTO users(org_id,dept_id,email,name,gender,password_hash,role,tz,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                     (org_id, dept_id, email, name, _gender(d.get("gender")), hash_password(password), role, _tz(d.get("tz")), ts()))
    record(db, "__register__", True)
    return _login_response(db, cur.lastrowid), 201


@bp.post("/auth/login")
def login():
    db, d = get_db(), body()
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    guard_login(db, email)
    u = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    ok = verify_password(u["password_hash"] if u else _DUMMY, password) and u is not None
    record(db, email, ok)
    if not ok:
        db.commit()
        raise ApiError("Неверная почта или пароль", 401)
    if not u["active"]:
        db.commit()
        raise ApiError("Аккаунт отключён. Обратитесь к администратору компании", 403)
    return _login_response(db, u["id"])


@bp.post("/auth/logout")
def logout():
    from flask import g
    u = current_user()
    if u:
        import hashlib
        get_db().execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(g.token.encode()).hexdigest(),))
    resp = jsonify(ok=True)
    clear_cookie(resp)
    return resp


@bp.patch("/me")
@login_required
def update_me():
    db, u, d = get_db(), current_user(), body()
    if "name" in d:
        db.execute("UPDATE users SET name=? WHERE id=?", (clean_name(d["name"]), u["id"]))
    if "gender" in d:
        db.execute("UPDATE users SET gender=? WHERE id=?", (_gender(d["gender"]), u["id"]))
    if "tz" in d:
        db.execute("UPDATE users SET tz=? WHERE id=?", (_tz(d["tz"]), u["id"]))
    if "dept_id" in d and u["org_id"]:
        if d["dept_id"] in (None, ""):
            db.execute("UPDATE users SET dept_id=NULL WHERE id=?", (u["id"],))
        else:
            dept = db.execute("SELECT id FROM departments WHERE id=? AND org_id=?", (d["dept_id"], u["org_id"])).fetchone()
            if not dept:
                raise ApiError("Выберите подразделение из списка", 400, "dept_id")
            db.execute("UPDATE users SET dept_id=? WHERE id=?", (dept["id"], u["id"]))
    return jsonify(user=me_payload(db, db.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()))


@bp.post("/me/password")
@login_required
def change_password():
    db, u, d = get_db(), current_user(), body()
    if not verify_password(u["password_hash"], d.get("current") or ""):
        raise ApiError("Текущий пароль указан неверно", 400, "current")
    check_password_rules(d.get("new"), u["email"])
    db.execute("UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?", (hash_password(d["new"]), u["id"]))
    from flask import g
    import hashlib
    # остальные сессии закрываем, текущую оставляем
    db.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?",
               (u["id"], hashlib.sha256(g.token.encode()).hexdigest()))
    return jsonify(ok=True)


@bp.post("/me/onboarded")
@login_required
def onboarded():
    get_db().execute("UPDATE users SET onboarded=1 WHERE id=?", (current_user()["id"],))
    return jsonify(ok=True)
