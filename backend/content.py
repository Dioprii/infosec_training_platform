"""Учебный контент: загрузка, публичное представление (без ответов), проверка ответов."""
import json


class ContentError(ValueError):
    pass


def validate_sel(q, sel):
    n = len(q["options"])
    if not isinstance(sel, list) or not sel or len(sel) > n:
        raise ContentError("Некорректный ответ")
    if any(isinstance(i, bool) or not isinstance(i, int) for i in sel):
        raise ContentError("Некорректный ответ")
    if q["type"] == "sort":
        if len(sel) != n or any(i not in (0, 1) for i in sel):
            raise ContentError("Отметьте каждый пункт")
    else:
        if any(i < 0 or i >= n for i in sel):
            raise ContentError("Некорректный вариант")
        if q["type"] in ("one", "tf") and len(sel) != 1:
            raise ContentError("Нужен один вариант")


def check(q, sel):
    validate_sel(q, sel)
    t = q["type"]
    if t in ("one", "tf"):
        return sel[0] == q["answer"]
    if t == "multi":
        return sorted(set(sel)) == sorted(q["answer"])
    return sel == q["answer"]  # sort


def correct_list(q):
    """Верный ответ в виде списка (для показа после ответа)."""
    return q["answer"] if isinstance(q["answer"], list) else [q["answer"]]


def public_question(q):
    return {"type": q["type"], "q": q["q"], "options": q["options"]}


class Course:
    def __init__(self, path):
        with open(path, encoding="utf-8") as f:
            self.data = json.load(f)
        d = self.data
        self.thresholds = d["thresholds"]
        self.levels = d["levels"]
        self.modules = {m["id"]: m for m in d["modules"]}
        self.lessons = {}
        self.bank = {}      # qid -> (module_id, topic, question)
        for m in d["modules"]:
            for les in m["lessons"]:
                self.lessons[les["key"]] = (m, les)
                for ci, ch in enumerate(les.get("chapters", [])):
                    for qi, q in enumerate(ch["questions"]):
                        self.bank[f"{les['key']}:{ci}:{qi}"] = (m["id"], m["topic"], q)
        self.daily = d["daily"]
        for i, q in enumerate(self.daily):
            self.bank[f"d:{i}"] = (0, q["topic"], q)
        self.total_lessons = len(self.lessons)
        self.max_level = len(self.levels)

    def level(self, stars):
        return min(self.max_level, sum(1 for t in self.thresholds if stars >= t))

    def lesson_questions(self, les):
        return [(ci, qi, q) for ci, ch in enumerate(les.get("chapters", []))
                for qi, q in enumerate(ch["questions"])]

    # --- что отдаём клиенту ---
    def outline(self):
        """Структура курса без содержимого уроков."""
        d = self.data
        return {
            "title": d["title"], "thresholds": self.thresholds, "levels": self.levels,
            "sections": d["sections"],
            "modules": [{"id": m["id"], "title": m["title"], "desc": m["desc"], "mascot": m["mascot"],
                         "topic": m["topic"], "short": m["short"], "unlock_level": m["unlock_level"],
                         "badge": m["badge"], "rules": m["rules"],
                         "lessons": [{"key": l["key"], "title": l["title"], "kind": l["kind"],
                                      "minutes": l["minutes"], "type": l["type"]} for l in m["lessons"]]}
                        for m in d["modules"]],
        }

    def public_lesson(self, key):
        m, les = self.lessons[key]
        out = {k: les[k] for k in ("key", "title", "kind", "minutes", "type")}
        out["module"] = m["id"]
        if les["type"] == "hotspot":
            h = les["hotspot"]
            out["material"] = les["material"]
            out["hotspot"] = {"need": h["need"], "hint": h["hint"],
                              "items": [{"id": i["id"], "text": i["text"]} for i in h["items"]]}
            return out
        chapters = []
        for ch in les["chapters"]:
            c = {k: ch[k] for k in ("title", "mascot", "intro", "material") }
            for k in ("mail", "cards", "story", "scene"):
                if k in ch:
                    c[k] = ch[k]
            c["questions"] = [public_question(q) for q in ch["questions"]]
            chapters.append(c)
        out["chapters"] = chapters
        return out
