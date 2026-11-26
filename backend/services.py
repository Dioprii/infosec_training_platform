"""Бизнес-логика: уровни, звёзды, серия дней, прогресс, награды."""
import datetime as dt
import random

from .db import get_db, parse_ts, ts, user_today, utcnow

DAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


# ---------- начисления ----------
def award(db, user, xp=0, stars=0, source=""):
    day = user_today(user["tz"]).isoformat()
    db.execute("INSERT INTO xp_log(user_id,xp,stars,source,ts,day) VALUES (?,?,?,?,?,?)",
               (user["id"], xp, stars, source, ts(), day))
    db.execute("UPDATE users SET xp=xp+?, stars=stars+? WHERE id=?", (xp, stars, user["id"]))


def touch_activity(db, user):
    day = user_today(user["tz"]).isoformat()
    db.execute("INSERT OR IGNORE INTO activity_days(user_id,day) VALUES (?,?)", (user["id"], day))
    cur = streak(db, user)["current"]
    if cur > user["best_streak"]:
        db.execute("UPDATE users SET best_streak=? WHERE id=?", (cur, user["id"]))


def streak(db, user):
    today = user_today(user["tz"])
    days = {r[0] for r in db.execute(
        "SELECT day FROM activity_days WHERE user_id=? ORDER BY day DESC LIMIT 400", (user["id"],))}
    d = today if today.isoformat() in days else today - dt.timedelta(days=1)
    cur = 0
    while d.isoformat() in days:
        cur += 1
        d -= dt.timedelta(days=1)
    monday = today - dt.timedelta(days=today.weekday())
    week = [{"d": DAY_NAMES[i], "active": (monday + dt.timedelta(days=i)).isoformat() in days,
             "today": i == today.weekday()} for i in range(7)]
    return {"current": cur, "best": max(cur, user["best_streak"]), "week": week}


# ---------- модули и доступ ----------
def module_states(course, stars, done_ids, gating):
    level = course.level(stars)
    locked = {}
    for k, m in course.modules.items():
        if gating == "sequential":
            locked[k] = k > 1 and (k - 1) not in done_ids
        else:
            locked[k] = level < m["unlock_level"]
    current = next((k for k in sorted(course.modules) if k not in done_ids and not locked[k]), 0)
    out = {}
    for k, m in course.modules.items():
        st = "done" if k in done_ids else "lock" if locked[k] else "cur" if k == current else "open"
        info = {"state": st}
        if st == "lock":
            if gating == "sequential":
                info["need"] = f"Сначала завершите неделю {k - 1}"
            else:
                need = course.thresholds[m["unlock_level"] - 1] - stars
                info["need"] = f"Откроется на уровне {m['unlock_level']}. Не хватает звёзд: {max(need, 0)}"
        out[k] = info
    return out, current


def user_org(db, user):
    return db.execute("SELECT * FROM orgs WHERE id=?", (user["org_id"],)).fetchone() if user["org_id"] else None


def gating_of(db, user):
    org = user_org(db, user)
    return org["gating"] if org else "level"


def done_modules(db, user_id):
    return {r[0] for r in db.execute("SELECT module_id FROM badges WHERE user_id=?", (user_id,))}


def lesson_rows(db, user_id):
    return {r["lesson_key"]: r for r in db.execute("SELECT * FROM lesson_progress WHERE user_id=?", (user_id,))}


def accuracy(db, user_id, course):
    rows = {r[0]: (r[1], r[2]) for r in db.execute(
        "SELECT topic, SUM(correct), COUNT(*) FROM answers WHERE user_id=? GROUP BY topic", (user_id,))}
    out = []
    for m in course.data["modules"]:
        ok, n = rows.get(m["topic"], (0, 0))
        out.append({"topic": m["topic"], "pct": round(100 * ok / n) if n else None, "answers": n})
    return out


def review_due(db, user_id, course, delay_hours, limit=None):
    """Вопросы, на которые последний ответ был неверным и прошло достаточно времени."""
    border = ts(utcnow() - dt.timedelta(hours=delay_hours))
    rows = db.execute("""SELECT a.qid FROM answers a
        JOIN (SELECT qid, MAX(id) AS mid FROM answers WHERE user_id=? GROUP BY qid) l ON l.mid=a.id
        WHERE a.correct=0 AND a.ts<=? ORDER BY a.ts""", (user_id, border)).fetchall()
    qids = [r[0] for r in rows if r[0] in course.bank]
    return qids[:limit] if limit else qids


def daily_index(user, course):
    return (user_today(user["tz"]).toordinal() + user["id"]) % len(course.daily)


def level_info(course, stars):
    lv = course.level(stars)
    th = course.thresholds
    if lv >= course.max_level:
        return lv, 100, 0
    span = th[lv] - th[lv - 1]
    return lv, round((stars - th[lv - 1]) / span * 100), th[lv] - stars


def progress_payload(db, user, course, cfg):
    u = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
    lp = lesson_rows(db, u["id"])
    done = done_modules(db, u["id"])
    gating = gating_of(db, u)
    states, current = module_states(course, u["stars"], done, gating)
    lv, pct, to_next = level_info(course, u["stars"])
    modules = {}
    for k, m in course.modules.items():
        n_done = sum(1 for l in m["lessons"] if lp.get(l["key"]) and lp[l["key"]]["done"])
        modules[k] = {**states[k], "lessons_done": n_done, "lessons_total": len(m["lessons"])}
    lessons = {key: {"done": bool(r["done"]), "best_trust": r["best_trust"], "stars": r["stars"],
                     "attempts": r["attempts"]} for key, r in lp.items()}
    cert = db.execute("SELECT code, issued_at FROM certificates WHERE user_id=?", (u["id"],)).fetchone()
    daily = db.execute("SELECT qi, pick, correct FROM daily_answers WHERE user_id=? AND day=?",
                       (u["id"], user_today(u["tz"]).isoformat())).fetchone()
    review_open = gating == "sequential" or lv >= 2
    exam_ok = (lv >= course.max_level) if gating == "level" else len(done) == len(course.modules)
    nxt = None
    if current:
        m = course.modules[current]
        left = len(m["lessons"]) - modules[current]["lessons_done"]
        nxt = {"module": current, "left": left, "badge": m["badge"]}
    return {
        "stars": u["stars"], "xp": u["xp"], "level": lv, "level_pct": pct, "stars_to_next": to_next,
        "streak": streak(db, u), "lessons": lessons, "modules": modules, "current": current,
        "badges": sorted(done), "accuracy": accuracy(db, u["id"], course), "next_badge": nxt,
        "review": {"open": review_open,
                   "due": len(review_due(db, u["id"], course, cfg["REVIEW_DELAY_HOURS"])) if review_open else 0},
        "daily": {"answered": bool(daily), "correct": bool(daily and daily["correct"])},
        "exam": {"open": bool(exam_ok), "passed": bool(cert)},
        "certificate": {"code": cert["code"], "issued_at": cert["issued_at"]} if cert else None,
        "gating": gating,
    }


def complete_lesson(db, user, course, key, hp, gain):
    """Фиксирует прохождение урока и считает награды. Возвращает словарь для клиента."""
    m, les = course.lessons[key]
    passed = hp >= 60
    row = db.execute("SELECT * FROM lesson_progress WHERE user_id=? AND lesson_key=?", (user["id"], key)).fetchone()
    old_best = row["best_trust"] if row else 0
    old_stars = row["stars"] if row else 0
    was_done = bool(row and row["done"])
    best = max(old_best, hp)
    target = (1 if best >= 60 else 0) + (1 if best >= 90 else 0)
    earn = max(0, target - old_stars)
    xp = (gain + (40 if passed else 0)) // (2 if was_done else 1)
    level_before = course.level(user["stars"])
    now = ts()
    if row:
        db.execute("""UPDATE lesson_progress SET best_trust=?, stars=?, attempts=attempts+1, last_at=?,
                      done=?, first_done_at=COALESCE(first_done_at, ?) WHERE user_id=? AND lesson_key=?""",
                   (best, old_stars + earn, now, int(was_done or passed), now if passed else None, user["id"], key))
    else:
        db.execute("""INSERT INTO lesson_progress(user_id,lesson_key,best_trust,stars,attempts,done,first_done_at,last_at)
                      VALUES (?,?,?,?,1,?,?,?)""", (user["id"], key, best, earn, int(passed), now if passed else None, now))
    award(db, user, xp=xp, stars=earn, source=f"lesson:{key}")
    touch_activity(db, user)
    badge, module_done = None, False
    if passed:
        keys = [l["key"] for l in m["lessons"]]
        n = db.execute(f"SELECT COUNT(*) FROM lesson_progress WHERE user_id=? AND done=1 AND lesson_key IN ({','.join('?'*len(keys))})",
                       [user["id"], *keys]).fetchone()[0]
        if n == len(keys) and not db.execute("SELECT 1 FROM badges WHERE user_id=? AND module_id=?", (user["id"], m["id"])).fetchone():
            db.execute("INSERT INTO badges(user_id,module_id,earned_at) VALUES (?,?,?)", (user["id"], m["id"], now))
            badge, module_done = m["badge"], True
    stars_now = user["stars"] + earn
    level_after = course.level(stars_now)
    return {"passed": passed, "hp": hp, "xp": xp, "stars_earned": earn, "replay": was_done,
            "level": level_after, "level_up": level_after if level_after > level_before else 0,
            "module_done": module_done, "badge": badge, "module": m["id"], "rules": m["rules"]}


def pick_exam(course, per_module, rng=random):
    qids = []
    for k in sorted(course.modules):
        pool = [qid for qid, (mid, _, _) in course.bank.items() if mid == k]
        qids += rng.sample(pool, min(per_module, len(pool)))
    rng.shuffle(qids)
    return qids
