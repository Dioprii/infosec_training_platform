"""Обучение: курс, уроки, ответы (проверяются на сервере), награды, экзамен, сертификат."""
import html
import json
import uuid

from flask import Blueprint, Response, current_app, jsonify

from . import services as sv
from .content import ContentError, check, correct_list, public_question
from .db import get_db, ts, user_today
from .routes_auth import me_payload
from .security import ApiError, body, current_user, login_required

bp = Blueprint("learn", __name__)


def course():
    return current_app.extensions["course"]


def cfg():
    return current_app.config


def _int(v, name="значение"):
    if isinstance(v, bool) or not isinstance(v, int):
        raise ApiError(f"Некорректное {name}")
    return v


def _unlocked(db, u, module_id):
    states, _ = sv.module_states(course(), u["stars"], sv.done_modules(db, u["id"]), sv.gating_of(db, u))
    if states[module_id]["state"] == "lock":
        raise ApiError(states[module_id]["need"], 403)


def _check(q, sel):
    try:
        return check(q, sel)
    except ContentError as e:
        raise ApiError(str(e))


# ---------- главные данные ----------
@bp.get("/bootstrap")
@login_required
def bootstrap():
    db, u = get_db(), current_user()
    return jsonify(user=me_payload(db, u), course=course().outline(),
                   progress=sv.progress_payload(db, u, course(), cfg()))


@bp.get("/progress")
@login_required
def progress():
    db, u = get_db(), current_user()
    return jsonify(sv.progress_payload(db, u, course(), cfg()))


@bp.get("/lessons/<key>")
@login_required
def lesson(key):
    c = course()
    if key not in c.lessons:
        raise ApiError("Урок не найден", 404)
    _unlocked(get_db(), current_user(), c.lessons[key][0]["id"])
    return jsonify(c.public_lesson(key))


# ---------- прохождение урока ----------
def _new_run(db, u, kind, ref, state):
    db.execute("DELETE FROM runs WHERE user_id=? AND kind=? AND ref IS ? AND finished_at IS NULL", (u["id"], kind, ref))
    rid = uuid.uuid4().hex
    db.execute("INSERT INTO runs(id,user_id,kind,ref,state,created_at) VALUES (?,?,?,?,?,?)",
               (rid, u["id"], kind, ref, json.dumps(state), ts()))
    return rid


def _load_run(db, u, rid):
    r = db.execute("SELECT * FROM runs WHERE id=? AND user_id=?", (rid, u["id"])).fetchone()
    if not r:
        raise ApiError("Попытка не найдена", 404)
    if r["finished_at"]:
        raise ApiError("Эта попытка уже завершена", 409)
    return r, json.loads(r["state"])


def _save(db, rid, st):
    db.execute("UPDATE runs SET state=? WHERE id=?", (json.dumps(st), rid))


@bp.post("/lessons/<key>/start")
@login_required
def start_lesson(key):
    db, u, c = get_db(), current_user(), course()
    if key not in c.lessons:
        raise ApiError("Урок не найден", 404)
    m, les = c.lessons[key]
    _unlocked(db, u, m["id"])
    if les["type"] == "hotspot":
        rid = _new_run(db, u, "hotspot", key, {"hp": 100, "found": [], "gain": 0})
    else:
        rid = _new_run(db, u, "lesson", key, {"hp": 100, "combo": 0, "sc": 0, "gain": 0, "hints": 2,
                                              "answered": {}, "removed": {}})
    return jsonify(run=rid, hints=2)


@bp.post("/runs/<rid>/answer")
@login_required
def run_answer(rid):
    db, u, c, d = get_db(), current_user(), course(), body()
    r, st = _load_run(db, u, rid)
    sel = d.get("sel")
    if r["kind"] == "lesson":
        m, les = c.lessons[r["ref"]]
        ci, qi = _int(d.get("ch"), "задание"), _int(d.get("qi"), "задание")
        try:
            q = les["chapters"][ci]["questions"][qi]
        except (IndexError, TypeError):
            raise ApiError("Такого задания нет", 404)
        k = f"{ci}:{qi}"
        if k in st["answered"]:
            raise ApiError("На этот вопрос вы уже ответили", 409)
        ok = _check(q, sel)
        st["answered"][k] = ok
        if ok:
            st["sc"] += 1
            st["combo"] += 1
            st["gain"] += 30 + 10 * min(st["combo"] - 1, 2)
        else:
            st["combo"] = 0
            st["hp"] = max(0, st["hp"] - 20)
        db.execute("INSERT INTO answers(user_id,qid,topic,correct,source,ts) VALUES (?,?,?,?,?,?)",
                   (u["id"], f"{r['ref']}:{ci}:{qi}", m["topic"], int(ok), "lesson", ts()))
        sv.touch_activity(db, u)
        _save(db, rid, st)
        return jsonify(ok=ok, text=q["ok"] if ok else q["no"], correct=correct_list(q),
                       hp=st["hp"], combo=st["combo"], gain=st["gain"], sc=st["sc"])
    if r["kind"] == "exam":
        qi = _int(d.get("qi"), "задание")
        if not 0 <= qi < len(st["qids"]):
            raise ApiError("Такого задания нет", 404)
        if str(qi) in st["answered"]:
            raise ApiError("На этот вопрос вы уже ответили", 409)
        mid, topic, q = c.bank[st["qids"][qi]]
        ok = _check(q, sel)
        st["answered"][str(qi)] = ok
        db.execute("INSERT INTO answers(user_id,qid,topic,correct,source,ts) VALUES (?,?,?,?,?,?)",
                   (u["id"], st["qids"][qi], topic, int(ok), "exam", ts()))
        _save(db, rid, st)
        return jsonify(recorded=True, answered=len(st["answered"]), total=len(st["qids"]))
    raise ApiError("Для этого задания ответы не принимаются")


@bp.post("/runs/<rid>/hint")
@login_required
def run_hint(rid):
    db, u, c, d = get_db(), current_user(), course(), body()
    r, st = _load_run(db, u, rid)
    if r["kind"] != "lesson":
        raise ApiError("Подсказки здесь недоступны")
    ci, qi = _int(d.get("ch")), _int(d.get("qi"))
    try:
        q = c.lessons[r["ref"]][1]["chapters"][ci]["questions"][qi]
    except (IndexError, TypeError):
        raise ApiError("Такого задания нет", 404)
    k = f"{ci}:{qi}"
    if k in st["answered"] or q["type"] not in ("one", "multi") or st["hints"] <= 0:
        raise ApiError("Подсказка недоступна")
    right = set(correct_list(q))
    gone = st["removed"].setdefault(k, [])
    wrong = next((i for i in range(len(q["options"])) if i not in right and i not in gone), None)
    if wrong is None:
        raise ApiError("Убирать больше нечего")
    gone.append(wrong)
    st["hints"] -= 1
    _save(db, rid, st)
    return jsonify(remove=wrong, hints=st["hints"])


@bp.post("/runs/<rid>/hit")
@login_required
def run_hit(rid):
    db, u, c, d = get_db(), current_user(), course(), body()
    r, st = _load_run(db, u, rid)
    if r["kind"] != "hotspot":
        raise ApiError("Здесь нечего отмечать")
    h = c.lessons[r["ref"]][1]["hotspot"]
    item = next((i for i in h["items"] if i["id"] == d.get("id")), None)
    if not item:
        raise ApiError("Такого элемента нет", 404)
    if item["id"] not in st["found"]:
        st["found"].append(item["id"])
        if item["ok"]:
            st["gain"] += 30
        else:
            st["hp"] = max(0, st["hp"] - 10)
        sv.touch_activity(db, u)
        _save(db, rid, st)
    n = sum(1 for i in h["items"] if i["ok"] and i["id"] in st["found"])
    return jsonify(ok=item["ok"], msg=item["msg"], found=n, need=h["need"], hp=st["hp"])


@bp.post("/runs/<rid>/finish")
@login_required
def run_finish(rid):
    db, u, c = get_db(), current_user(), course()
    r, st = _load_run(db, u, rid)
    if r["kind"] == "lesson":
        total = len(c.lesson_questions(c.lessons[r["ref"]][1]))
        if len(st["answered"]) < total:
            raise ApiError("Ответьте на все вопросы урока")
        hp = st["hp"] if st["sc"] * 2 >= total else min(st["hp"], 59)   # меньше половины верных: не засчитываем
        res = sv.complete_lesson(db, u, c, r["ref"], hp, st["gain"])
        res.update(sc=st["sc"], total=total)
    elif r["kind"] == "hotspot":
        h = c.lessons[r["ref"]][1]["hotspot"]
        if sum(1 for i in h["items"] if i["ok"] and i["id"] in st["found"]) < h["need"]:
            raise ApiError("Найдены не все признаки")
        res = sv.complete_lesson(db, u, c, r["ref"], st["hp"], st["gain"])
        res.update(sc=h["need"], total=h["need"])
    else:
        return _finish_exam(db, u, c, r, st)
    db.execute("UPDATE runs SET finished_at=? WHERE id=?", (ts(), rid))
    res["progress"] = sv.progress_payload(db, db.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone(), c, cfg())
    return jsonify(res)


# ---------- вопрос дня ----------
@bp.get("/daily")
@login_required
def daily():
    db, u, c = get_db(), current_user(), course()
    qi = sv.daily_index(u, c)
    q = c.daily[qi]
    row = db.execute("SELECT * FROM daily_answers WHERE user_id=? AND day=?",
                     (u["id"], user_today(u["tz"]).isoformat())).fetchone()
    out = {"q": q["q"], "options": q["options"], "answered": None}
    if row:
        out["answered"] = {"pick": row["pick"], "ok": bool(row["correct"]), "correct": q["answer"],
                           "text": q["ok"] if row["correct"] else q["no"]}
    return jsonify(out)


@bp.post("/daily/answer")
@login_required
def daily_answer():
    db, u, c, d = get_db(), current_user(), course(), body()
    qi = sv.daily_index(u, c)
    q = c.daily[qi]
    day = user_today(u["tz"]).isoformat()
    if db.execute("SELECT 1 FROM daily_answers WHERE user_id=? AND day=?", (u["id"], day)).fetchone():
        raise ApiError("Сегодня вы уже отвечали на вопрос дня", 409)
    pick = _int(d.get("pick"), "ответ")
    ok = _check({**q, "type": "one"}, [pick])
    db.execute("INSERT INTO daily_answers(user_id,day,qi,pick,correct) VALUES (?,?,?,?,?)", (u["id"], day, qi, pick, int(ok)))
    db.execute("INSERT INTO answers(user_id,qid,topic,correct,source,ts) VALUES (?,?,?,?,?,?)",
               (u["id"], f"d:{qi}", q["topic"], int(ok), "daily", ts()))
    level_before = c.level(u["stars"])
    if ok:
        sv.award(db, u, xp=20, stars=1, source="daily")
    sv.touch_activity(db, u)
    level_after = c.level(u["stars"] + (1 if ok else 0))
    return jsonify(ok=ok, text=q["ok"] if ok else q["no"], correct=q["answer"],
                   level_up=level_after if level_after > level_before else 0)


# ---------- повторение ошибок ----------
@bp.get("/review")
@login_required
def review():
    db, u, c = get_db(), current_user(), course()
    p = sv.gating_of(db, u)
    if p == "level" and c.level(u["stars"]) < 2:
        raise ApiError("Тренажёр «Повторение ошибок» откроется на уровне 2", 403)
    due = sv.review_due(db, u["id"], c, cfg()["REVIEW_DELAY_HOURS"])
    items = []
    for qid in due[:5]:
        _, topic, q = c.bank[qid]
        items.append({"qid": qid, "topic": topic, **public_question({**q, "type": q.get("type", "one")})})
    return jsonify(due=len(due), questions=items)


@bp.post("/review/answer")
@login_required
def review_answer():
    db, u, c, d = get_db(), current_user(), course(), body()
    qid = d.get("qid")
    if qid not in sv.review_due(db, u["id"], c, cfg()["REVIEW_DELAY_HOURS"]):
        raise ApiError("Этот вопрос сейчас не нужно повторять", 409)
    _, topic, q = c.bank[qid]
    q = {**q, "type": q.get("type", "one")}
    ok = _check(q, d.get("sel"))
    db.execute("INSERT INTO answers(user_id,qid,topic,correct,source,ts) VALUES (?,?,?,?,?,?)",
               (u["id"], qid, topic, int(ok), "review", ts()))
    if ok:
        sv.award(db, u, xp=10, source="review")
    sv.touch_activity(db, u)
    return jsonify(ok=ok, text=q["ok"] if ok else q["no"], correct=correct_list(q), xp=10 if ok else 0)


# ---------- команда ----------
@bp.get("/team")
@login_required
def team():
    db, u = get_db(), current_user()
    if not u["org_id"]:
        return jsonify(enabled=False)
    today = user_today(u["tz"])
    monday = (today - __import__("datetime").timedelta(days=today.weekday())).isoformat()
    rows = db.execute("""SELECT d.id, d.name, COALESCE(SUM(x.xp),0) AS pts FROM departments d
        LEFT JOIN users us ON us.dept_id=d.id AND us.active=1
        LEFT JOIN xp_log x ON x.user_id=us.id AND x.day>=?
        WHERE d.org_id=? GROUP BY d.id ORDER BY pts DESC, d.name""", (monday, u["org_id"])).fetchall()
    return jsonify(enabled=len(rows) > 1, my_dept=u["dept_id"],
                   departments=[{"id": r["id"], "name": r["name"], "points": r["pts"]} for r in rows])


# ---------- экзамен и сертификат ----------
def _exam_state(db, u, c):
    p = sv.progress_payload(db, u, c, cfg())
    return p


@bp.get("/exam")
@login_required
def exam_info():
    db, u, c = get_db(), current_user(), course()
    p = sv.progress_payload(db, u, c, cfg())
    last = db.execute("SELECT score,total,passed,created_at FROM exam_attempts WHERE user_id=? ORDER BY id DESC LIMIT 1",
                      (u["id"],)).fetchone()
    return jsonify(open=p["exam"]["open"], passed=p["exam"]["passed"], certificate=p["certificate"],
                   total=len(c.modules) * cfg()["EXAM_QUESTIONS_PER_MODULE"], pass_share=cfg()["EXAM_PASS_SHARE"],
                   gating=p["gating"], last=dict(last) if last else None)


@bp.post("/exam/start")
@login_required
def exam_start():
    db, u, c = get_db(), current_user(), course()
    p = sv.progress_payload(db, u, c, cfg())
    if not p["exam"]["open"]:
        raise ApiError("Итоговый экзамен откроется на уровне 8", 403)
    qids = sv.pick_exam(c, cfg()["EXAM_QUESTIONS_PER_MODULE"])
    rid = _new_run(db, u, "exam", None, {"qids": qids, "answered": {}})
    qs = []
    for qid in qids:
        _, topic, q = c.bank[qid]
        qs.append({**public_question({**q, "type": q.get("type", "one")}), "topic": topic})
    return jsonify(run=rid, questions=qs)


def _finish_exam(db, u, c, r, st):
    total = len(st["qids"])
    if len(st["answered"]) < total:
        raise ApiError("Ответьте на все вопросы экзамена")
    score = sum(1 for v in st["answered"].values() if v)
    passed = score / total >= cfg()["EXAM_PASS_SHARE"]
    db.execute("INSERT INTO exam_attempts(user_id,score,total,passed,created_at) VALUES (?,?,?,?,?)",
               (u["id"], score, total, int(passed), ts()))
    db.execute("UPDATE runs SET finished_at=? WHERE id=?", (ts(), r["id"]))
    review = []
    for i, qid in enumerate(st["qids"]):
        if not st["answered"][str(i)]:
            _, topic, q = c.bank[qid]
            review.append({"q": q["q"], "options": q["options"], "type": q.get("type", "one"),
                           "correct": correct_list(q), "text": q["ok"], "topic": topic})
    cert = None
    if passed:
        cert = db.execute("SELECT code FROM certificates WHERE user_id=?", (u["id"],)).fetchone()
        if not cert:
            import secrets
            code = "SK-" + secrets.token_hex(5).upper()
            org = sv.user_org(db, u)
            db.execute("INSERT INTO certificates(code,user_id,holder_name,org_name,score,issued_at) VALUES (?,?,?,?,?,?)",
                       (code, u["id"], u["name"], org["name"] if org else None, round(100 * score / total), ts()))
            sv.award(db, u, xp=200, stars=2, source="exam")
            cert = {"code": code}
        sv.touch_activity(db, u)
    return jsonify(score=score, total=total, passed=passed, review=review,
                   certificate=cert["code"] if cert else None)


def certificate_page(code):
    db = get_db()
    row = db.execute("SELECT * FROM certificates WHERE code=?", (code.upper(),)).fetchone()
    if not row:
        return Response("<h1>Сертификат не найден</h1>", 404, mimetype="text/html; charset=utf-8")
    e = html.escape
    date = row["issued_at"][:10]
    d = ".".join(reversed(date.split("-")))
    org = f"<p class='org'>{e(row['org_name'])}</p>" if row["org_name"] else ""
    page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Сертификат {e(row['code'])}</title>
<style>
body{{margin:0;background:#F5F3EC;color:#1B2A5C;font:400 17px/1.5 Onest,system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;padding:20px;box-sizing:border-box}}
.sheet{{background:#fff;max-width:880px;width:100%;border:10px solid #1B2A5C;border-radius:6px;padding:46px 40px;text-align:center;box-sizing:border-box;outline:3px solid #6FAE2E;outline-offset:-22px}}
img{{height:170px}}h1{{font-size:38px;margin:10px 0 4px;line-height:1.15}}.sub{{color:#5B6585}}
.name{{font-size:36px;font-weight:800;margin:22px 0 4px;color:#3F7A12}}.org{{margin:0;color:#5B6585}}
.meta{{margin-top:30px;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;font-size:14px;color:#5B6585}}
button{{margin-top:22px;background:#6FAE2E;border:0;border-radius:12px;padding:12px 22px;font:800 16px inherit;color:#10230A;cursor:pointer}}
@media print{{body{{background:#fff}}button{{display:none}}}}
</style></head><body><div><div class="sheet">
<img src="/assets/mascot/turtle-8.webp" alt="">
<h1>Сертификат о прохождении курса</h1>
<p class="sub">«Основы информационной безопасности» · Северный Контур, Академия безопасности</p>
<p class="sub" style="margin-top:26px">Подтверждаем, что</p>
<div class="name">{e(row['holder_name'])}</div>{org}
<p style="margin-top:18px">успешно прошёл(-ла) итоговый экзамен с результатом {row['score']}%</p>
<div class="meta"><span>Дата выдачи: {d}</span><span>Номер: {e(row['code'])}</span></div>
</div><div style="text-align:center"><button onclick="print()">Распечатать или сохранить в PDF</button></div></div></body></html>"""
    return Response(page, mimetype="text/html; charset=utf-8")
