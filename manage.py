#!/usr/bin/env python3
"""Управляющие команды.

  python manage.py create-org "Название" "Имя Админа" admin@company.ru   # создать компанию и администратора
  python manage.py reset-password user@company.ru                        # новый временный пароль
  python manage.py seed-demo                                             # демо-компания с сотрудниками (для показа)
"""
import random
import secrets
import sys

from backend import create_app
from backend.db import get_db, ts
from backend.routes_auth import new_invite_code
from backend.security import hash_password


def cmd_create_org(name, admin_name, email):
    db = get_db()
    temp = secrets.token_urlsafe(9)
    code = new_invite_code(db)
    org = db.execute("INSERT INTO orgs(name,invite_code,created_at) VALUES (?,?,?)", (name, code, ts())).lastrowid
    db.execute("INSERT INTO departments(org_id,name) VALUES (?,?)", (org, "Все сотрудники"))
    db.execute("""INSERT INTO users(org_id,email,name,password_hash,role,must_change_password,created_at)
                  VALUES (?,?,?,?,'admin',1,?)""", (org, email.lower(), admin_name, hash_password(temp), ts()))
    print(f"Компания создана. Код для сотрудников: {code}\nАдминистратор: {email}\nВременный пароль: {temp}")


def cmd_reset(email):
    db = get_db()
    temp = secrets.token_urlsafe(9)
    n = db.execute("UPDATE users SET password_hash=?, must_change_password=1 WHERE email=?",
                   (hash_password(temp), email.lower())).rowcount
    if not n:
        sys.exit("Пользователь не найден")
    db.execute("DELETE FROM sessions WHERE user_id=(SELECT id FROM users WHERE email=?)", (email.lower(),))
    print(f"Временный пароль для {email}: {temp}")


FIRST = ["Анна", "Игорь", "Мария", "Сергей", "Елена", "Дмитрий", "Наталья", "Алексей", "Ирина", "Павел",
         "Ольга", "Андрей", "Татьяна", "Михаил", "Юлия", "Виктор", "Светлана", "Роман", "Екатерина", "Максим",
         "Вера", "Глеб", "Алиса", "Артём"]
DEPTS = [("HR", .9), ("Бухгалтерия", .8), ("Менеджеры", .75), ("Поддержка", .65), ("Склад", .5)]


def cmd_seed(app):
    from backend import services as sv
    db, c = get_db(), app.extensions["course"]
    if db.execute("SELECT 1 FROM users WHERE email='admin@severny-kontur.ru'").fetchone():
        sys.exit("Демо-данные уже созданы")
    rnd = random.Random(7)
    org = db.execute("INSERT INTO orgs(name,invite_code,created_at) VALUES (?,?,?)",
                     ("Северный Контур", "DEMO2026", ts())).lastrowid
    dept_ids = {n: db.execute("INSERT INTO departments(org_id,name) VALUES (?,?)", (org, n)).lastrowid for n, _ in DEPTS}
    pw = hash_password("Demo-Pass-2026")
    db.execute("INSERT INTO users(org_id,email,name,password_hash,role,onboarded,created_at) VALUES (?,?,?,?,?,1,?)",
               (org, "admin@severny-kontur.ru", "Анатолий Рябов", pw, "admin", ts()))
    lessons = [l["key"] for m in c.data["modules"] for l in m["lessons"]]
    import datetime as dt
    for i, nm in enumerate(FIRST):
        dname, strength = DEPTS[i % len(DEPTS)]
        uid = db.execute("""INSERT INTO users(org_id,dept_id,email,name,password_hash,onboarded,created_at)
                            VALUES (?,?,?,?,?,1,?)""",
                         (org, dept_ids[dname], f"user{i + 1}@severny-kontur.ru", f"{nm} {chr(1040 + i)}.", pw, ts())).lastrowid
        done_n = min(21, max(0, int(rnd.gauss(strength * 21, 4))))
        stars = xp = 0
        for key in lessons[:done_n]:
            trust = rnd.choice([100, 100, 80, 80, 60])
            st = 1 + (trust >= 90)
            stars += st
            xp += 60 + rnd.randint(0, 60)
            db.execute("INSERT INTO lesson_progress VALUES (?,?,?,?,1,1,?,?)", (uid, key, trust, st, ts(), ts()))
            m = c.lessons[key][0]
            topic = m["topic"]
            for _ in range(2):
                ok = rnd.random() < {"Фишинг": .55, "Wi-Fi и удалёнка": .6, "Пароли и 2FA": .8}.get(topic, .75)
                db.execute("INSERT INTO answers(user_id,qid,topic,correct,source,ts) VALUES (?,?,?,?,?,?)",
                           (uid, f"{key}:0:0", topic, int(ok), "lesson", ts()))
        for k, m in c.modules.items():
            if all(l["key"] in lessons[:done_n] for l in m["lessons"]):
                db.execute("INSERT INTO badges VALUES (?,?,?)", (uid, k, ts()))
        db.execute("UPDATE users SET stars=?, xp=? WHERE id=?", (stars, xp, uid))
        today = dt.date.today()
        for back in rnd.sample(range(14), rnd.randint(2, 11)):
            day = (today - dt.timedelta(days=back)).isoformat()
            db.execute("INSERT OR IGNORE INTO activity_days VALUES (?,?)", (uid, day))
            db.execute("INSERT INTO xp_log(user_id,xp,stars,source,ts,day) VALUES (?,?,0,'demo',?,?)",
                       (uid, rnd.randint(20, 120), ts(), day))
    print("Готово.\n  Администратор: admin@severny-kontur.ru\n  Сотрудники: user1@severny-kontur.ru ... user24@severny-kontur.ru\n"
          "  Пароль у всех: Demo-Pass-2026   (код компании: DEMO2026)\n  Не используйте демо-данные в рабочей среде!")


def main():
    app = create_app()
    args = sys.argv[1:]
    with app.app_context():
        db = get_db()
        if args[:1] == ["create-org"] and len(args) == 4:
            cmd_create_org(*args[1:])
        elif args[:1] == ["reset-password"] and len(args) == 2:
            cmd_reset(args[1])
        elif args[:1] == ["seed-demo"]:
            cmd_seed(app)
        else:
            print(__doc__)
            return
        db.commit()


if __name__ == "__main__":
    main()
