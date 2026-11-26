"""Кабинет администратора компании. Ответы отдельных людей наружу не отдаются:
по людям виден только прогресс (недели, звёзды, активность), по ошибкам только сводка."""
import csv
import datetime as dt
import io
import secrets

from flask import Blueprint, Response, current_app, jsonify

from . import services as sv
from .db import get_db, ts, utcnow
from .routes_auth import new_invite_code
from .security import ApiError, admin_required, body, clean_name, current_user

bp = Blueprint("admin", __name__)


def _course():
    return current_app.extensions["course"]


def _people(db, org_id):
    """Сотрудники организации с агрегатами прогресса."""
    c = _course()
    rows = db.execute("""
      SELECT u.id,u.name,u.email,u.role,u.active,u.dept_id,u.stars,u.xp,u.created_at,d.name AS dept,
        (SELECT COUNT(*) FROM lesson_progress l WHERE l.user_id=u.id AND l.done=1) AS lessons,
        (SELECT COUNT(*) FROM badges b WHERE b.user_id=u.id) AS weeks,
        (SELECT MAX(day) FROM activity_days a WHERE a.user_id=u.id) AS last_active,
        (SELECT 1 FROM certificates ce WHERE ce.user_id=u.id) AS cert
      FROM users u LEFT JOIN departments d ON d.id=u.dept_id
      WHERE u.org_id=? ORDER BY u.name COLLATE NOCASE""", (org_id,)).fetchall()
    out = []
    for r in rows:
        out.append({"id": r["id"], "name": r["name"], "email": r["email"], "role": r["role"],
                    "active": bool(r["active"]), "dept_id": r["dept_id"], "dept": r["dept"],
                    "lessons": r["lessons"], "progress": round(100 * r["lessons"] / c.total_lessons),
                    "weeks": r["weeks"], "stars": r["stars"], "xp": r["xp"], "level": c.level(r["stars"]),
                    "last_active": r["last_active"], "certified": bool(r["cert"]), "created_at": r["created_at"][:10]})
    return out


@bp.get("/overview")
@admin_required
def overview():
    db, u, c = get_db(), current_user(), _course()
    people = [p for p in _people(db, u["org_id"]) if p["active"]]
    n = len(people)
    week_ago = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    active7 = sum(1 for p in people if p["last_active"] and p["last_active"] >= week_ago)
    depts = [dict(r) for r in db.execute("SELECT id,name FROM departments WHERE org_id=? ORDER BY name", (u["org_id"],))]
    groups = [{"id": d["id"], "name": d["name"]} for d in depts]
    if any(p["dept_id"] is None for p in people):
        groups.append({"id": None, "name": "Без подразделения"})
    for g in groups:
        m = [p for p in people if p["dept_id"] == g["id"]]
        g["members"] = len(m)
        g["progress"] = round(sum(p["progress"] for p in m) / len(m)) if m else 0
        g["completed"] = sum(1 for p in m if p["weeks"] == len(c.modules))
    ids = [p["id"] for p in people]
    mods = []
    for k, m in c.modules.items():
        done = db.execute(f"SELECT COUNT(*) FROM badges WHERE module_id=? AND user_id IN ({','.join('?'*len(ids)) or 'NULL'})",
                          [k, *ids]).fetchone()[0] if ids else 0
        mods.append({"id": k, "title": m["title"], "short": m["short"], "share": round(100 * done / n) if n else 0})
    # ошибки: только сводка по теме, и только когда в выборке достаточно людей
    errors = {"hidden": True, "min_group": current_app.config["MIN_GROUP"], "topics": []}
    if ids:
        marks = ",".join("?" * len(ids))
        who = db.execute(f"SELECT COUNT(DISTINCT user_id) FROM answers WHERE user_id IN ({marks})", ids).fetchone()[0]
        if who >= current_app.config["MIN_GROUP"]:
            rows = db.execute(f"""SELECT topic, COUNT(*) n, SUM(1-correct) bad FROM answers
                                  WHERE user_id IN ({marks}) GROUP BY topic HAVING n>=5""", ids).fetchall()
            errors = {"hidden": False, "topics": sorted(
                [{"topic": r["topic"], "answers": r["n"], "error_rate": round(100 * r["bad"] / r["n"])} for r in rows],
                key=lambda x: -x["error_rate"])}
    since = (dt.date.today() - dt.timedelta(days=13)).isoformat()
    act = {r[0]: r[1] for r in db.execute(
        f"""SELECT day, COUNT(*) FROM activity_days WHERE day>=? AND user_id IN ({','.join('?'*len(ids)) or 'NULL'}) GROUP BY day""",
        [since, *ids])} if ids else {}
    activity = [{"day": (dt.date.today() - dt.timedelta(days=13 - i)).isoformat(),
                 "users": act.get((dt.date.today() - dt.timedelta(days=13 - i)).isoformat(), 0)} for i in range(14)]
    org = db.execute("SELECT name FROM orgs WHERE id=?", (u["org_id"],)).fetchone()
    return jsonify(org=org["name"], employees=n, started=sum(1 for p in people if p["lessons"] or p["last_active"]),
                   active7=active7, completed=sum(1 for p in people if p["weeks"] == len(c.modules)),
                   certified=sum(1 for p in people if p["certified"]),
                   progress=round(sum(p["progress"] for p in people) / n) if n else 0,
                   departments=groups, modules=mods, errors=errors, activity=activity)


@bp.get("/users")
@admin_required
def users():
    return jsonify(users=_people(get_db(), current_user()["org_id"]))


def _target(db, me, uid):
    t = db.execute("SELECT * FROM users WHERE id=? AND org_id=?", (uid, me["org_id"])).fetchone()
    if not t:
        raise ApiError("Сотрудник не найден", 404)
    return t


def _other_admins(db, me, uid):
    return db.execute("SELECT COUNT(*) FROM users WHERE org_id=? AND role='admin' AND active=1 AND id<>?",
                      (me["org_id"], uid)).fetchone()[0]


@bp.patch("/users/<int:uid>")
@admin_required
def patch_user(uid):
    db, me, d = get_db(), current_user(), body()
    t = _target(db, me, uid)
    if "dept_id" in d:
        if d["dept_id"] is None:
            db.execute("UPDATE users SET dept_id=NULL WHERE id=?", (uid,))
        else:
            if not db.execute("SELECT 1 FROM departments WHERE id=? AND org_id=?", (d["dept_id"], me["org_id"])).fetchone():
                raise ApiError("Подразделение не найдено", 404)
            db.execute("UPDATE users SET dept_id=? WHERE id=?", (d["dept_id"], uid))
    new_role = d.get("role", t["role"])
    new_active = int(bool(d["active"])) if "active" in d else t["active"]
    if new_role not in ("learner", "admin"):
        raise ApiError("Неизвестная роль")
    if (new_role != "admin" or not new_active) and t["role"] == "admin" and t["active"] and not _other_admins(db, me, uid):
        raise ApiError("Нельзя убрать последнего администратора компании", 400)
    db.execute("UPDATE users SET role=?, active=? WHERE id=?", (new_role, new_active, uid))
    if not new_active:
        db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    return jsonify(ok=True)


@bp.post("/users/<int:uid>/reset-password")
@admin_required
def reset_password(uid):
    from .security import hash_password
    db, me = get_db(), current_user()
    _target(db, me, uid)
    temp = secrets.token_urlsafe(9)
    db.execute("UPDATE users SET password_hash=?, must_change_password=1 WHERE id=?", (hash_password(temp), uid))
    db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    return jsonify(temp_password=temp)


# ---------- подразделения ----------
@bp.get("/departments")
@admin_required
def departments():
    rows = get_db().execute("""SELECT d.id,d.name,COUNT(u.id) members FROM departments d
        LEFT JOIN users u ON u.dept_id=d.id WHERE d.org_id=? GROUP BY d.id ORDER BY d.name""",
                            (current_user()["org_id"],)).fetchall()
    return jsonify(departments=[dict(r) for r in rows])


@bp.post("/departments")
@admin_required
def add_department():
    db, me = get_db(), current_user()
    name = clean_name(body().get("name"), "название подразделения")
    if db.execute("SELECT 1 FROM departments WHERE org_id=? AND name=?", (me["org_id"], name)).fetchone():
        raise ApiError("Такое подразделение уже есть", 409)
    cur = db.execute("INSERT INTO departments(org_id,name) VALUES (?,?)", (me["org_id"], name))
    return jsonify(id=cur.lastrowid, name=name), 201


@bp.patch("/departments/<int:did>")
@admin_required
def rename_department(did):
    db, me = get_db(), current_user()
    name = clean_name(body().get("name"), "название подразделения")
    if not db.execute("SELECT 1 FROM departments WHERE id=? AND org_id=?", (did, me["org_id"])).fetchone():
        raise ApiError("Подразделение не найдено", 404)
    if db.execute("SELECT 1 FROM departments WHERE org_id=? AND name=? AND id<>?", (me["org_id"], name, did)).fetchone():
        raise ApiError("Такое подразделение уже есть", 409)
    db.execute("UPDATE departments SET name=? WHERE id=?", (name, did))
    return jsonify(ok=True)


@bp.delete("/departments/<int:did>")
@admin_required
def delete_department(did):
    db, me = get_db(), current_user()
    if not db.execute("SELECT 1 FROM departments WHERE id=? AND org_id=?", (did, me["org_id"])).fetchone():
        raise ApiError("Подразделение не найдено", 404)
    db.execute("DELETE FROM departments WHERE id=?", (did,))   # сотрудники остаются без подразделения
    return jsonify(ok=True)


# ---------- настройки компании ----------
@bp.get("/org")
@admin_required
def org_get():
    o = get_db().execute("SELECT name,invite_code,gating,allowed_domain FROM orgs WHERE id=?", (current_user()["org_id"],)).fetchone()
    return jsonify(dict(o))


@bp.patch("/org")
@admin_required
def org_patch():
    db, me, d = get_db(), current_user(), body()
    if "name" in d:
        db.execute("UPDATE orgs SET name=? WHERE id=?", (clean_name(d["name"], "название компании"), me["org_id"]))
    if "gating" in d:
        if d["gating"] not in ("level", "sequential"):
            raise ApiError("Неизвестный режим открытия недель")
        db.execute("UPDATE orgs SET gating=? WHERE id=?", (d["gating"], me["org_id"]))
    if "allowed_domain" in d:
        dom = (d["allowed_domain"] or "").strip().lower().lstrip("@")
        if dom and ("." not in dom or " " in dom or "/" in dom):
            raise ApiError("Укажите домен, например company.ru", 400, "allowed_domain")
        db.execute("UPDATE orgs SET allowed_domain=? WHERE id=?", (dom or None, me["org_id"]))
    return org_get()


@bp.post("/org/regenerate-code")
@admin_required
def regen_code():
    db, me = get_db(), current_user()
    db.execute("UPDATE orgs SET invite_code=? WHERE id=?", (new_invite_code(db), me["org_id"]))
    return org_get()


@bp.get("/export.csv")
@admin_required
def export_csv():
    def safe(v):
        s = "" if v is None else str(v)
        return "'" + s if s[:1] in "=+-@\t\r" else s
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["Имя", "Почта", "Подразделение", "Роль", "Статус", "Пройдено уроков", "Прогресс, %",
                "Недель пройдено", "Звёзд", "Уровень", "Последняя активность", "Сертификат"])
    for p in _people(get_db(), current_user()["org_id"]):
        w.writerow([safe(p["name"]), safe(p["email"]), safe(p["dept"] or ""), "админ" if p["role"] == "admin" else "сотрудник",
                    "активен" if p["active"] else "отключён", p["lessons"], p["progress"], p["weeks"], p["stars"],
                    p["level"], p["last_active"] or "", "да" if p["certified"] else "нет"])
    data = "\ufeff" + out.getvalue()      # BOM, чтобы Excel открыл кириллицу
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=progress.csv"})
