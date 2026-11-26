import os
import tempfile
import unittest

from backend import create_app


def right(q):
    a = q["answer"]
    return a if isinstance(a, list) else [a]


def wrong(q):
    n = len(q["options"])
    if q["type"] == "sort":
        return [1 - v for v in q["answer"]]
    if q["type"] == "multi":
        return [next(i for i in range(n) if i not in q["answer"])]
    return [(q["answer"] + 1) % n]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({"DB_PATH": os.path.join(self.tmp, "t.db"), "TESTING": True})
        self.c = self.app.extensions["course"]
        self.cl = self.app.test_client()

    def api(self, method, url, data=None, client=None, status=None, **kw):
        cl = client or self.cl
        r = getattr(cl, method)("/api" + url, json=data if method != "get" else None, **kw)
        if status:
            self.assertEqual(r.status_code, status, r.get_data(as_text=True))
        return r

    def register(self, email="olga@example.com", name="Ольга", mode="individual", client=None, **extra):
        d = {"mode": mode, "name": name, "email": email, "password": "Зелёный-Чайник-7", **extra}
        return self.api("post", "/auth/register", d, client=client, status=201)

    def solve(self, key, mistakes=0, client=None):
        m, les = self.c.lessons[key]
        r = self.api("post", f"/lessons/{key}/start", {}, client=client, status=200).get_json()["run"]
        if les["type"] == "hotspot":
            for it in les["hotspot"]["items"]:
                if it["ok"]:
                    self.api("post", f"/runs/{r}/hit", {"id": it["id"]}, client=client, status=200)
        else:
            left = mistakes
            for ci, qi, q in self.c.lesson_questions(les):
                sel = wrong(q) if left > 0 else right(q)
                left -= 1
                self.api("post", f"/runs/{r}/answer", {"ch": ci, "qi": qi, "sel": sel}, client=client, status=200)
        return self.api("post", f"/runs/{r}/finish", {}, client=client, status=200).get_json()


class AuthTests(Base):
    def test_register_login_logout(self):
        self.assertIsNone(self.api("get", "/session").get_json()["user"])
        self.register()
        me = self.api("get", "/session").get_json()["user"]
        self.assertEqual(me["name"], "Ольга")
        self.api("post", "/auth/logout", {}, status=200)
        self.api("get", "/bootstrap", status=401)
        self.api("post", "/auth/login", {"email": "OLGA@example.com", "password": "Зелёный-Чайник-7"}, status=200)
        self.api("get", "/bootstrap", status=200)

    def test_validation(self):
        base = {"mode": "individual", "name": "A", "email": "a@b.ru", "password": "Зелёный-Чайник-7"}
        self.api("post", "/auth/register", {**base, "password": "short"}, status=400)
        self.api("post", "/auth/register", {**base, "password": "password"}, status=400)
        self.api("post", "/auth/register", {**base, "email": "nope"}, status=400)
        self.api("post", "/auth/register", {**base, "mode": "x"}, status=400)
        self.api("post", "/auth/register", base, status=201)
        self.api("post", "/auth/register", base, client=self.app.test_client(), status=409)

    def test_login_rate_limit_and_generic_error(self):
        self.register()
        c2 = self.app.test_client()
        for _ in range(8):
            r = self.api("post", "/auth/login", {"email": "olga@example.com", "password": "bad-bad-bad"}, client=c2, status=401)
        self.assertEqual(r.get_json()["error"], "Неверная почта или пароль")
        self.api("post", "/auth/login", {"email": "olga@example.com", "password": "Зелёный-Чайник-7"}, client=c2, status=429)

    def test_foreign_origin_rejected(self):
        self.api("post", "/auth/login", {"email": "a@b.ru", "password": "x"}, headers={"Origin": "https://evil.example"}, status=403)

    def test_org_flow(self):
        admin = self.app.test_client()
        self.register("boss@corp.ru", "Босс", "create_org", client=admin, org_name="Корп", departments="HR, Склад")
        code = self.api("get", "/admin/org", client=admin).get_json()["invite_code"]
        lk = self.api("get", f"/orgs/lookup?code={code.lower()}", status=200).get_json()
        self.assertEqual(lk["name"], "Корп")
        self.api("get", "/orgs/lookup?code=ZZZZZZZZ", status=404)
        emp = self.app.test_client()
        dept = lk["departments"][0]["id"]
        self.register("emp@corp.ru", "Сотрудник", "join", client=emp, invite_code=code, dept_id=dept)
        self.assertEqual(self.api("get", "/session", client=emp).get_json()["user"]["org"]["name"], "Корп")
        self.api("get", "/admin/overview", client=emp, status=403)
        self.api("get", "/admin/overview", client=admin, status=200)
        self.api("patch", "/admin/org", {"allowed_domain": "corp.ru"}, client=admin, status=200)
        self.api("post", "/auth/register", {"mode": "join", "name": "X", "email": "x@gmail.com",
                                            "password": "Зелёный-Чайник-7", "invite_code": code},
                 client=self.app.test_client(), status=400)

    def test_cross_org_isolation(self):
        a, b = self.app.test_client(), self.app.test_client()
        self.register("a@a.ru", "A", "create_org", client=a, org_name="Аа")
        self.register("b@b.ru", "B", "create_org", client=b, org_name="Бб")
        uid_b = self.api("get", "/admin/users", client=b).get_json()["users"][0]["id"]
        self.api("patch", f"/admin/users/{uid_b}", {"active": False}, client=a, status=404)
        self.api("post", f"/admin/users/{uid_b}/reset-password", {}, client=a, status=404)


class LearnTests(Base):
    def setUp(self):
        super().setUp()
        self.register()

    def test_public_content_has_no_answers(self):
        data = self.api("get", "/lessons/1.0", status=200).get_json()
        s = str(data)
        self.assertNotIn("'answer'", s)
        self.assertNotIn("'ok':", s.replace("'ok': ", "'ok':"))  # объяснений тоже нет
        self.assertTrue(all(ch["material"] for ch in data["chapters"]))
        hot = self.api("get", "/lessons/2.0").get_json()
        self.assertNotIn("'ok'", str(hot))

    def test_every_lesson_has_material_and_questions(self):
        for key, (m, les) in self.c.lessons.items():
            if les["type"] == "hotspot":
                self.assertTrue(les["material"])
            else:
                for ch in les["chapters"]:
                    self.assertTrue(ch["material"] and ch["questions"], key)

    def test_locked_module(self):
        self.api("get", "/lessons/3.0", status=403)
        self.api("post", "/lessons/4.1/start", {}, status=403)

    def test_lesson_flow_and_stars(self):
        r = self.solve("1.1")
        self.assertTrue(r["passed"])
        self.assertEqual(r["stars_earned"], 2)
        self.assertEqual(r["progress"]["stars"], 2)
        self.assertGreater(r["progress"]["xp"], 0)
        self.assertTrue(r["progress"]["lessons"]["1.1"]["done"])

    def test_replay_gives_missing_star_only(self):
        r1 = self.solve("1.1", mistakes=1)       # одна ошибка: доверие 80%, одна звезда
        self.assertEqual((r1["hp"], r1["stars_earned"]), (80, 1))
        r2 = self.solve("1.1")
        self.assertEqual(r2["stars_earned"], 1)  # дополучили вторую
        r3 = self.solve("1.1")
        self.assertEqual(r3["stars_earned"], 0)
        self.assertEqual(self.api("get", "/progress").get_json()["stars"], 2)

    def test_failed_lesson_not_done(self):
        m, les = self.c.lessons["7.2"]
        # 7.2 в закрытом модуле: проверяем на открытом 1.2 с тремя ошибками
        r = self.solve("1.2", mistakes=5)
        self.assertFalse(r["passed"])
        self.assertEqual(r["stars_earned"], 0)
        self.assertFalse(r["progress"]["lessons"]["1.2"]["done"])

    def test_cannot_finish_early_or_double_answer(self):
        run = self.api("post", "/lessons/1.0/start", {}).get_json()["run"]
        self.api("post", f"/runs/{run}/finish", {}, status=400)
        q = self.c.lessons["1.0"][1]["chapters"][0]["questions"][0]
        self.api("post", f"/runs/{run}/answer", {"ch": 0, "qi": 0, "sel": right(q)}, status=200)
        self.api("post", f"/runs/{run}/answer", {"ch": 0, "qi": 0, "sel": right(q)}, status=409)
        self.api("post", f"/runs/{run}/answer", {"ch": 9, "qi": 0, "sel": [0]}, status=404)
        self.api("post", f"/runs/{run}/answer", {"ch": 0, "qi": 1, "sel": [99]}, status=400)

    def test_other_user_cannot_use_run(self):
        run = self.api("post", "/lessons/1.0/start", {}).get_json()["run"]
        other = self.app.test_client()
        self.register("b@example.com", "Б", client=other)
        self.api("post", f"/runs/{run}/finish", {}, client=other, status=404)

    def test_hint(self):
        run = self.api("post", "/lessons/1.0/start", {}).get_json()["run"]
        h = self.api("post", f"/runs/{run}/hint", {"ch": 0, "qi": 0}, status=200).get_json()
        q = self.c.lessons["1.0"][1]["chapters"][0]["questions"][0]
        self.assertNotEqual(h["remove"], q["answer"])
        self.assertEqual(h["hints"], 1)

    def test_module_badge_and_level_unlock(self):
        for key in ("1.0", "1.1", "1.2"):
            last = self.solve(key)
        self.assertTrue(last["module_done"])
        self.assertEqual(last["badge"]["code"], "Пр")
        self.assertIn(1, last["progress"]["badges"])
        for key in ("2.0", "2.1", "2.2"):
            last = self.solve(key)
        p = last["progress"]
        self.assertEqual(p["modules"]["2"]["state"], "done")
        self.assertGreaterEqual(p["level"], 3)
        self.assertEqual(p["modules"]["3"]["state"], "cur")
        self.api("get", "/lessons/3.0", status=200)

    def test_hotspot_wrong_click_costs_trust(self):
        run = self.api("post", "/lessons/2.0/start", {}).get_json()["run"]
        self.assertFalse(self.api("post", f"/runs/{run}/hit", {"id": "d"}).get_json()["ok"])
        for i in "abc":
            self.api("post", f"/runs/{run}/hit", {"id": i}, status=200)
        r = self.api("post", f"/runs/{run}/finish", {}).get_json()
        self.assertEqual(r["hp"], 90)
        self.assertEqual(r["stars_earned"], 2)

    def test_daily_once_per_day(self):
        d = self.api("get", "/daily").get_json()
        self.assertIsNone(d["answered"])
        r = self.api("post", "/daily/answer", {"pick": 1}, status=200).get_json()
        self.assertTrue(r["ok"])
        self.assertEqual(self.api("get", "/progress").get_json()["stars"], 1)
        self.api("post", "/daily/answer", {"pick": 1}, status=409)
        self.assertTrue(self.api("get", "/daily").get_json()["answered"]["ok"])

    def test_streak_and_activity(self):
        self.solve("1.1")
        s = self.api("get", "/progress").get_json()["streak"]
        self.assertEqual(s["current"], 1)
        self.assertEqual(sum(1 for d in s["week"] if d["active"]), 1)

    def test_review_flow(self):
        self.api("get", "/review", status=403)  # нужен уровень 2
        for key in ("1.0", "1.1"):
            self.solve(key)                      # уровень 2: 3 звезды+
        self.solve("1.2", mistakes=1)
        self.assertEqual(self.api("get", "/review", status=200).get_json()["due"], 0)  # ещё рано
        self.app.config["REVIEW_DELAY_HOURS"] = 0
        rv = self.api("get", "/review").get_json()
        self.assertGreaterEqual(rv["due"], 1)
        item = rv["questions"][0]
        qid = item["qid"]
        q = self.c.bank[qid][2]
        r = self.api("post", "/review/answer", {"qid": qid, "sel": right(q)}, status=200).get_json()
        self.assertTrue(r["ok"])
        self.assertEqual(self.api("get", "/review").get_json()["due"], rv["due"] - 1)

    def test_exam_and_certificate(self):
        self.api("post", "/exam/start", {}, status=403)
        from backend.db import get_db
        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE users SET stars=42")
            db.commit()
        self.assertTrue(self.api("get", "/exam").get_json()["open"])
        ex = self.api("post", "/exam/start", {}, status=200).get_json()
        self.assertEqual(len(ex["questions"]), 14)
        self.assertNotIn("answer", str(ex))
        # провал: все неверно
        run = ex["run"]
        with self.app.app_context():
            import json
            row = get_db().execute("SELECT state FROM runs WHERE id=?", (run,)).fetchone()
            qids = json.loads(row["state"])["qids"]
        for i, qid in enumerate(qids):
            self.api("post", f"/runs/{run}/answer", {"qi": i, "sel": wrong(self.c.bank[qid][2])}, status=200)
        r = self.api("post", f"/runs/{run}/finish", {}, status=200).get_json()
        self.assertFalse(r["passed"])
        self.assertEqual(len(r["review"]), 14)
        # успех
        ex = self.api("post", "/exam/start", {}).get_json()
        run = ex["run"]
        with self.app.app_context():
            qids = json.loads(get_db().execute("SELECT state FROM runs WHERE id=?", (run,)).fetchone()["state"])["qids"]
        for i, qid in enumerate(qids):
            self.api("post", f"/runs/{run}/answer", {"qi": i, "sel": right(self.c.bank[qid][2])}, status=200)
        r = self.api("post", f"/runs/{run}/finish", {}, status=200).get_json()
        self.assertTrue(r["passed"])
        code = r["certificate"]
        page = self.cl.get(f"/certificate/{code}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Ольга", page.get_data(as_text=True))
        self.assertEqual(self.cl.get("/certificate/SK-NOPE").status_code, 404)

    def test_xss_name_escaped_in_certificate(self):
        self.api("patch", "/me", {"name": "<script>alert(1)</script>"}, status=200)
        from backend.db import get_db
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO certificates VALUES ('SK-TEST1',1,'<b>x</b>',NULL,90,'2026-01-01 00:00:00')")
            db.commit()
        self.assertNotIn("<b>x</b>", self.cl.get("/certificate/SK-TEST1").get_data(as_text=True))


class AdminTests(Base):
    def test_overview_privacy_and_export(self):
        admin = self.app.test_client()
        self.register("boss@corp.ru", "Босс", "create_org", client=admin, org_name="Корп", departments="HR, Склад")
        code = self.api("get", "/admin/org", client=admin).get_json()["invite_code"]
        depts = self.api("get", "/admin/departments", client=admin).get_json()["departments"]
        emps = []
        for i in range(3):
            c = self.app.test_client()
            self.register(f"e{i}@corp.ru", f"Сотр{i}", "join", client=c, invite_code=code, dept_id=depts[i % 2]["id"])
            emps.append(c)
        ov = self.api("get", "/admin/overview", client=admin).get_json()
        self.assertEqual(ov["employees"], 4)
        self.assertTrue(ov["errors"]["hidden"])
        for c in emps:
            self.solve("1.1", mistakes=1, client=c)
        ov = self.api("get", "/admin/overview", client=admin).get_json()
        self.assertFalse(ov["errors"]["hidden"])
        self.assertEqual(ov["errors"]["topics"][0]["topic"], "Пароли и 2FA")
        csv = self.api("get", "/admin/export.csv", client=admin)
        self.assertIn("Сотр0", csv.get_data(as_text=True))
        users = self.api("get", "/admin/users", client=admin).get_json()["users"]
        self.assertNotIn("answers", str(users))
        # сброс пароля и отключение
        target = next(u for u in users if u["email"] == "e0@corp.ru")
        tmp = self.api("post", f"/admin/users/{target['id']}/reset-password", {}, client=admin).get_json()["temp_password"]
        self.api("get", "/bootstrap", client=emps[0], status=401)
        r = self.api("post", "/auth/login", {"email": "e0@corp.ru", "password": tmp}, client=emps[0], status=200)
        self.assertTrue(r.get_json()["user"]["must_change_password"])
        self.api("patch", f"/admin/users/{target['id']}", {"active": False}, client=admin, status=200)
        self.api("post", "/auth/login", {"email": "e0@corp.ru", "password": tmp}, client=self.app.test_client(), status=403)
        me = next(u for u in users if u["role"] == "admin")
        self.api("patch", f"/admin/users/{me['id']}", {"role": "learner"}, client=admin, status=400)

    def test_gating_sequential(self):
        admin = self.app.test_client()
        self.register("boss@corp.ru", "Босс", "create_org", client=admin, org_name="Корп")
        self.api("get", "/lessons/3.0", client=admin, status=403)
        self.api("patch", "/admin/org", {"gating": "sequential"}, client=admin, status=200)
        for k in ("1.0", "1.1", "1.2", "2.0", "2.1", "2.2"):
            self.solve(k, client=admin)
        self.api("get", "/lessons/3.0", client=admin, status=200)
        self.api("get", "/lessons/4.0", client=admin, status=403)

    def test_team_board(self):
        admin = self.app.test_client()
        self.register("boss@corp.ru", "Босс", "create_org", client=admin, org_name="Корп", departments="HR, Склад")
        self.solve("1.1", client=admin)
        t = self.api("get", "/team", client=admin).get_json()
        self.assertTrue(t["enabled"])
        self.assertEqual(t["departments"][0]["name"] in ("HR", "Склад"), True)
        solo = self.app.test_client()
        self.register("solo@x.ru", "S", client=solo)
        self.assertFalse(self.api("get", "/team", client=solo).get_json()["enabled"])


if __name__ == "__main__":
    unittest.main()
