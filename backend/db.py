"""SQLite: схема, подключение, вспомогательные функции времени."""
import datetime as dt
import sqlite3
from zoneinfo import ZoneInfo

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  invite_code TEXT NOT NULL UNIQUE,
  gating TEXT NOT NULL DEFAULT 'level',          -- level | sequential
  allowed_domain TEXT,                           -- например severny-kontur.ru
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS departments(
  id INTEGER PRIMARY KEY,
  org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  UNIQUE(org_id, name)
);
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY,
  org_id INTEGER REFERENCES orgs(id) ON DELETE SET NULL,
  dept_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  gender TEXT,                                   -- f | m | NULL
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'learner',          -- learner | admin
  active INTEGER NOT NULL DEFAULT 1,
  must_change_password INTEGER NOT NULL DEFAULT 0,
  onboarded INTEGER NOT NULL DEFAULT 0,
  tz TEXT NOT NULL DEFAULT 'Europe/Moscow',
  stars INTEGER NOT NULL DEFAULT 0,
  xp INTEGER NOT NULL DEFAULT 0,
  best_streak INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  last_login TEXT
);
CREATE INDEX IF NOT EXISTS users_org ON users(org_id);
CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  ua TEXT
);
CREATE TABLE IF NOT EXISTS login_attempts(
  id INTEGER PRIMARY KEY,
  email TEXT, ip TEXT, ok INTEGER NOT NULL, ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS la_ts ON login_attempts(ts);
CREATE TABLE IF NOT EXISTS lesson_progress(
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  lesson_key TEXT NOT NULL,
  best_trust INTEGER NOT NULL DEFAULT 0,
  stars INTEGER NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  done INTEGER NOT NULL DEFAULT 0,
  first_done_at TEXT,
  last_at TEXT,
  PRIMARY KEY(user_id, lesson_key)
);
CREATE TABLE IF NOT EXISTS badges(
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  module_id INTEGER NOT NULL,
  earned_at TEXT NOT NULL,
  PRIMARY KEY(user_id, module_id)
);
CREATE TABLE IF NOT EXISTS answers(
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  qid TEXT NOT NULL, topic TEXT NOT NULL,
  correct INTEGER NOT NULL, source TEXT NOT NULL, ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS answers_uq ON answers(user_id, qid, ts);
CREATE TABLE IF NOT EXISTS xp_log(
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  xp INTEGER NOT NULL DEFAULT 0, stars INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL, ts TEXT NOT NULL, day TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS xp_day ON xp_log(day);
CREATE TABLE IF NOT EXISTS activity_days(
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  day TEXT NOT NULL,
  PRIMARY KEY(user_id, day)
);
CREATE TABLE IF NOT EXISTS daily_answers(
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  day TEXT NOT NULL, qi INTEGER NOT NULL, pick INTEGER NOT NULL, correct INTEGER NOT NULL,
  PRIMARY KEY(user_id, day)
);
CREATE TABLE IF NOT EXISTS runs(
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,                             -- lesson | hotspot | exam
  ref TEXT,                                       -- ключ урока
  state TEXT NOT NULL,
  created_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS exam_attempts(
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  score INTEGER NOT NULL, total INTEGER NOT NULL, passed INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS certificates(
  code TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  holder_name TEXT NOT NULL, org_name TEXT, score INTEGER NOT NULL, issued_at TEXT NOT NULL
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"], timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        if exc is None:
            db.commit()
        else:
            db.rollback()
        db.close()


def init_db(path):
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    if "gender" not in [r[1] for r in con.execute("PRAGMA table_info(users)")]:
        con.execute("ALTER TABLE users ADD COLUMN gender TEXT")
    con.commit()
    con.close()


# ---------- время ----------
def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def ts(t=None):
    """UTC-строка 'YYYY-MM-DD HH:MM:SS' (сравнивается как текст)."""
    return (t or utcnow()).strftime("%Y-%m-%d %H:%M:%S")


def parse_ts(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)


def user_today(tz_name, t=None):
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = dt.timezone.utc
    return (t or utcnow()).astimezone(tz).date()
