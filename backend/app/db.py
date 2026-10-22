"""SQLite access: one short-lived connection per use, versioned migrations, demo seed."""
from __future__ import annotations

import random
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta

from .config import Settings
from .domain import today, week_start

V1 = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_en TEXT NOT NULL,
    balance INTEGER NOT NULL DEFAULT 0, points INTEGER NOT NULL DEFAULT 0, phone TEXT);
CREATE TABLE IF NOT EXISTS pacts(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), type TEXT NOT NULL,
    target_days INTEGER NOT NULL, stake INTEGER NOT NULL, daily_goal INTEGER, active INTEGER NOT NULL DEFAULT 1, created TEXT, ends TEXT);
CREATE TABLE IF NOT EXISTS checkins(id INTEGER PRIMARY KEY, pact_id INTEGER NOT NULL REFERENCES pacts(id), day TEXT NOT NULL,
    value INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS txns(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), amount INTEGER NOT NULL,
    kind TEXT NOT NULL, day TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settlements(week TEXT PRIMARY KEY, pool INTEGER, fee INTEGER, charity INTEGER, winners INTEGER)
"""
V2 = """
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS otps(phone TEXT PRIMARY KEY, code_hash TEXT NOT NULL, expires INTEGER NOT NULL, tries INTEGER NOT NULL DEFAULT 0,
    locked_until INTEGER NOT NULL DEFAULT 0, win_start INTEGER NOT NULL DEFAULT 0, sent INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS users_phone ON users(phone);
CREATE UNIQUE INDEX IF NOT EXISTS pacts_one_active ON pacts(user_id, type) WHERE active=1;
CREATE INDEX IF NOT EXISTS pacts_user ON pacts(user_id, active);
CREATE INDEX IF NOT EXISTS checkins_pact_day ON checkins(pact_id, day);
CREATE INDEX IF NOT EXISTS checkins_day ON checkins(day, pact_id);
CREATE INDEX IF NOT EXISTS txns_user ON txns(user_id, id);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS sessions_expires ON sessions(expires)
"""
# columns that MVP-era databases lack; SQLite cannot ADD a UNIQUE column, so uniqueness lives in the indexes above
ADD_COLS = [("users", "phone", "TEXT"), ("pacts", "created", "TEXT"), ("pacts", "ends", "TEXT"),
            ("otps", "locked_until", "INTEGER NOT NULL DEFAULT 0"), ("otps", "win_start", "INTEGER NOT NULL DEFAULT 0"),
            ("otps", "sent", "INTEGER NOT NULL DEFAULT 0")]


@contextmanager
def db(path: str, write: bool = False):
    """One connection per use, always closed. write=True takes the write lock up front (BEGIN IMMEDIATE) so
    check-then-act sequences cannot interleave; commits on success, rolls back on any error."""
    con = sqlite3.connect(path, timeout=5, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA synchronous=NORMAL")  # safe with WAL, avoids an fsync per commit
    try:
        if write:
            con.execute("BEGIN IMMEDIATE")
        yield con
        if write:
            con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def _script(con, sql: str):
    for stmt in sql.split(";"):
        if stmt.strip():
            con.execute(stmt)


def migrate(con):
    """Versioned: each step runs once. Idempotent steps are still written defensively (IF NOT EXISTS), so a half-applied
    step on a dev database is repaired instead of crashing."""
    v = con.execute("PRAGMA user_version").fetchone()[0]
    if v < 1:
        _script(con, V1)  # MVP databases already have these tables; IF NOT EXISTS leaves them alone
        _add_columns(con)
        con.execute("PRAGMA user_version=1")
    if v < 2:
        _script(con, V2)
        _add_columns(con)  # otps now exists too
        con.execute("PRAGMA user_version=2")
    if v < 3:
        # Last line of defence for the money invariants: whatever the app code does, a balance or points total can never go negative.
        con.execute("""CREATE TRIGGER IF NOT EXISTS users_money_floor BEFORE UPDATE OF balance, points ON users
                       WHEN NEW.balance < 0 OR NEW.points < 0 BEGIN SELECT RAISE(ABORT, 'negative'); END""")
        con.execute("PRAGMA user_version=3")
    if v < 4:  # every pact carries its own daily goal; older rows only had one for steps
        con.execute("UPDATE pacts SET daily_goal=30 WHERE daily_goal IS NULL AND type='gym'")
        con.execute("UPDATE pacts SET daily_goal=3 WHERE daily_goal IS NULL AND type='nutrition'")
        con.execute("UPDATE pacts SET daily_goal=8000 WHERE daily_goal IS NULL AND type='steps'")
        con.execute("PRAGMA user_version=4")


def _add_columns(con):
    for table, col, ddl in ADD_COLS:
        have = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}  # nosec B608 - constants only
        if have and col not in have:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")  # nosec B608 - constants only


def init(st: Settings):
    with db(st.db_path) as con:
        con.execute("PRAGMA journal_mode=WAL")  # persistent, and illegal inside a transaction
    with db(st.db_path, write=True) as con:
        migrate(con)
        # Weeks before the first boot are never settled retroactively.
        con.execute("INSERT OR IGNORE INTO meta VALUES('epoch', ?)", (week_start(today(st.zone)).isoformat(),))
        if st.demo and not con.execute("SELECT 1 FROM users").fetchone():
            seed(con, today(st.zone))


def seed(con, tod: date):
    """Demo data: 9 users with phones 0912000000{1..9}; user 1 is the demo 'you'."""
    rnd = random.Random(7)  # nosec B311 - deterministic demo data, not security-relevant
    people = [("آرش", "Arash"), ("نگار", "Negar"), ("سینا", "Sina"), ("مهسا", "Mahsa"), ("کاوه", "Kaveh"),
              ("ترانه", "Taraneh"), ("بردیا", "Bardia"), ("شیرین", "Shirin"), ("پویا", "Pouya")]
    for i, (fa, en) in enumerate(people, 1):
        con.execute("INSERT INTO users(id,name,name_en,balance,points,phone) VALUES(?,?,?,?,?,?)",
                    (i, fa, en, 1_250_000 if i == 1 else rnd.randrange(3, 30) * 100_000, rnd.randrange(80, 900), f"0912000000{i}"))
        kinds = [("gym", 4, 50_000, 30), ("steps", 5, 30_000, 8000), ("nutrition", 6, 20_000, 3)] if i == 1 else rnd.sample(
            [("gym", rnd.randint(3, 5), rnd.choice([30_000, 50_000, 100_000]), 30),
             ("steps", rnd.randint(4, 7), rnd.choice([20_000, 50_000]), rnd.choice([6000, 8000, 10000])),
             ("nutrition", rnd.randint(4, 7), rnd.choice([20_000, 40_000]), 3)], rnd.randint(1, 2))
        for kind, days, stake, goal in kinds:
            pid = con.execute("INSERT INTO pacts(user_id,type,target_days,stake,daily_goal,created) VALUES(?,?,?,?,?,?)",
                              (i, kind, days, stake, goal, (tod - timedelta(28)).isoformat())).lastrowid
            for back in range(1, 22):  # three weeks of history, excluding today
                if rnd.random() < (0.8 if i == 1 else 0.6):
                    d = (tod - timedelta(back)).isoformat()
                    for v in {"gym": [rnd.choice([35, 45, 60, 75])], "steps": [rnd.randrange(5000, 13000)], "nutrition": [1, 1, 1]}[kind]:
                        con.execute("INSERT INTO checkins(pact_id,day,value) VALUES(?,?,?)", (pid, d, v))
    for back, amount, kind in [(9, 1_000_000, "topup"), (6, 84_000, "reward"), (2, -30_000, "penalty")]:
        con.execute("INSERT INTO txns(user_id,amount,kind,day) VALUES(?,?,?,?)", (1, amount, kind, (tod - timedelta(back)).isoformat()))
    for r in con.execute("SELECT u.id, u.balance - COALESCE((SELECT SUM(amount) FROM txns WHERE user_id=u.id), 0) AS gap FROM users u").fetchall():
        if r["gap"]:  # the ledger must explain every balance, demo included
            con.execute("INSERT INTO txns(user_id,amount,kind,day) VALUES(?,?,?,?)", (r["id"], r["gap"], "topup", (tod - timedelta(20)).isoformat()))
