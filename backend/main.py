import os
import random
import sqlite3
from datetime import date, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DB = os.getenv("DB_PATH", "pact.db")
FEE = 0.12  # service fee taken from the pool (business plan: 10–15%)
ME = 1  # ponytail: single demo user, add OTP auth before real money moves
THRESHOLD = {"gym": 30, "nutrition": 3}  # per-day goal; steps uses pact.daily_goal

app = FastAPI(title="FitPeyman API")


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def week_start(d: date) -> date:  # Iranian week starts on Saturday
    return d - timedelta((d.weekday() - 5) % 7)


def settle(pacts):
    """pacts: [{id, stake, target_days, done_days}] -> ({pact_id: delta}, fee, charity).
    Missed days pay stake each; winners split the pool minus fee by stake; leftover goes to charity."""
    deltas = {p["id"]: -p["stake"] * (p["target_days"] - p["done_days"]) for p in pacts if p["done_days"] < p["target_days"]}
    pool = -sum(deltas.values())
    fee = round(pool * FEE)
    winners = [p for p in pacts if p["done_days"] >= p["target_days"]]
    total = sum(p["stake"] for p in winners)
    for p in winners:
        deltas[p["id"]] = (pool - fee) * p["stake"] // total
    charity = pool - fee - sum(v for v in deltas.values() if v > 0)
    return deltas, fee, charity


def init():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, name_en TEXT, balance INTEGER, points INTEGER);
    CREATE TABLE IF NOT EXISTS pacts(id INTEGER PRIMARY KEY, user_id INTEGER, type TEXT, target_days INTEGER,
        stake INTEGER, daily_goal INTEGER, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS checkins(id INTEGER PRIMARY KEY, pact_id INTEGER, day TEXT, value INTEGER, note TEXT);
    CREATE TABLE IF NOT EXISTS txns(id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER, kind TEXT, day TEXT);
    CREATE TABLE IF NOT EXISTS settlements(week TEXT PRIMARY KEY, pool INTEGER, fee INTEGER, charity INTEGER, winners INTEGER);
    """)
    if con.execute("SELECT 1 FROM users").fetchone():
        return con.close()
    rnd, today = random.Random(7), date.today()
    people = [("آرش", "Arash"), ("نگار", "Negar"), ("سینا", "Sina"), ("مهسا", "Mahsa"), ("کاوه", "Kaveh"),
              ("ترانه", "Taraneh"), ("بردیا", "Bardia"), ("شیرین", "Shirin"), ("پویا", "Pouya")]
    for i, (fa, en) in enumerate(people, 1):
        con.execute("INSERT INTO users VALUES(?,?,?,?,?)", (i, fa, en, 1_250_000 if i == ME else rnd.randrange(3, 30) * 100_000, rnd.randrange(80, 900)))
        kinds = [("gym", 4, 50_000, None), ("steps", 5, 30_000, 8000), ("nutrition", 6, 20_000, None)] if i == ME else rnd.sample(
            [("gym", rnd.randint(3, 5), rnd.choice([30_000, 50_000, 100_000]), None),
             ("steps", rnd.randint(4, 7), rnd.choice([20_000, 50_000]), rnd.choice([6000, 8000, 10000])),
             ("nutrition", rnd.randint(4, 7), rnd.choice([20_000, 40_000]), None)], rnd.randint(1, 2))
        for kind, days, stake, goal in kinds:
            pid = con.execute("INSERT INTO pacts(user_id,type,target_days,stake,daily_goal) VALUES(?,?,?,?,?)", (i, kind, days, stake, goal)).lastrowid
            for back in range(1, 22):  # three weeks of history, excluding today
                if rnd.random() < (0.8 if i == ME else 0.6):
                    d = (today - timedelta(back)).isoformat()
                    for v in {"gym": [rnd.choice([35, 45, 60, 75])], "steps": [rnd.randrange(5000, 13000)], "nutrition": [1, 1, 1]}[kind]:
                        con.execute("INSERT INTO checkins(pact_id,day,value) VALUES(?,?,?)", (pid, d, v))
    for back, amount, kind in [(9, 1_000_000, "topup"), (6, 84_000, "reward"), (2, -30_000, "penalty")]:
        con.execute("INSERT INTO txns(user_id,amount,kind,day) VALUES(?,?,?,?)", (ME, amount, kind, (today - timedelta(back)).isoformat()))
    con.commit()
    con.close()


def done_days(con, p, start: date, end: date):
    """Days in [start, end] where this pact met its daily threshold."""
    goal = p["daily_goal"] if p["type"] == "steps" else THRESHOLD[p["type"]]
    agg = "SUM(value)" if p["type"] != "nutrition" else "COUNT(*)"
    rows = con.execute(f"SELECT day FROM checkins WHERE pact_id=? AND day BETWEEN ? AND ? GROUP BY day HAVING {agg} >= ?",
                       (p["id"], start.isoformat(), end.isoformat(), goal)).fetchall()
    return {r["day"] for r in rows}


def pact_view(con, p):
    today, start = date.today(), week_start(date.today())
    done = done_days(con, p, start, today)
    goal = p["daily_goal"] if p["type"] == "steps" else THRESHOLD[p["type"]]
    agg = "COALESCE(SUM(value),0)" if p["type"] != "nutrition" else "COUNT(*)"
    now = con.execute(f"SELECT {agg} FROM checkins WHERE pact_id=? AND day=?", (p["id"], today.isoformat())).fetchone()[0]
    return {**dict(p), "goal": goal, "today": now, "done_days": len(done), "days": sorted(done),
            "at_risk": max(0, p["target_days"] - len(done)) * p["stake"]}


def active_pacts(con, user_id=None):
    q = "SELECT * FROM pacts WHERE active=1" + (" AND user_id=?" if user_id else "")
    return [pact_view(con, p) for p in con.execute(q, (user_id,) if user_id else ())]


def streak(con, pacts):
    days = set().union(*(done_days(con, p, date.today() - timedelta(365), date.today()) for p in pacts)) if pacts else set()
    d, n = date.today(), 0
    if d.isoformat() not in days:
        d -= timedelta(1)
    while d.isoformat() in days:
        n, d = n + 1, d - timedelta(1)
    return n


def pool_view(con):
    pacts = active_pacts(con)
    deltas, fee, charity = settle(pacts)
    return {"amount": sum(-v for v in deltas.values() if v < 0), "fee": fee, "charity": charity, "fee_rate": FEE,
            "participants": len({p["user_id"] for p in pacts}),
            "on_track": sum(p["done_days"] >= p["target_days"] for p in pacts), "pacts": len(pacts)}


init()


@app.get("/api/dashboard")
def dashboard():
    con = db()
    u = dict(con.execute("SELECT * FROM users WHERE id=?", (ME,)).fetchone())
    pacts = active_pacts(con, ME)
    start = week_start(date.today())
    return {"user": {**u, "streak": streak(con, pacts)}, "pacts": pacts, "pool": pool_view(con),
            "week": [(start + timedelta(i)).isoformat() for i in range(7)], "today": date.today().isoformat()}


class NewPact(BaseModel):
    type: Literal["gym", "steps", "nutrition"]
    target_days: int = Field(ge=1, le=7)
    stake: int = Field(ge=10_000, le=1_000_000)
    daily_goal: int | None = Field(None, ge=1000, le=40_000)


@app.post("/api/pacts")
def create_pact(body: NewPact):
    con = db()
    if con.execute("SELECT 1 FROM pacts WHERE user_id=? AND type=? AND active=1", (ME, body.type)).fetchone():
        raise HTTPException(409, "exists")
    goal = (body.daily_goal or 8000) if body.type == "steps" else None
    pid = con.execute("INSERT INTO pacts(user_id,type,target_days,stake,daily_goal) VALUES(?,?,?,?,?)",
                      (ME, body.type, body.target_days, body.stake, goal)).lastrowid
    con.commit()
    return pact_view(con, con.execute("SELECT * FROM pacts WHERE id=?", (pid,)).fetchone())


class CheckIn(BaseModel):
    value: int = Field(ge=1, le=100_000)
    note: str | None = Field(None, max_length=60)


@app.post("/api/pacts/{pid}/checkin")
def checkin(pid: int, body: CheckIn):
    con = db()
    p = con.execute("SELECT * FROM pacts WHERE id=? AND user_id=? AND active=1", (pid, ME)).fetchone()
    if not p:
        raise HTTPException(404, "not_found")
    before = pact_view(con, p)
    value = 1 if p["type"] == "nutrition" else body.value
    con.execute("INSERT INTO checkins(pact_id,day,value,note) VALUES(?,?,?,?)", (pid, date.today().isoformat(), value, body.note))
    after = pact_view(con, p)
    if after["done_days"] > before["done_days"]:  # crossed today's goal
        con.execute("UPDATE users SET points=points+10 WHERE id=?", (ME,))
    con.commit()
    return after


REWARDS = [{"id": "gym20", "cost": 300}, {"id": "coach", "cost": 500}, {"id": "bottle", "cost": 200}, {"id": "charity", "cost": 100}]


@app.get("/api/wallet")
def wallet():
    con = db()
    u = con.execute("SELECT balance, points FROM users WHERE id=?", (ME,)).fetchone()
    txns = con.execute("SELECT * FROM txns WHERE user_id=? ORDER BY id DESC LIMIT 30", (ME,)).fetchall()
    return {**dict(u), "txns": [dict(t) for t in txns], "rewards": REWARDS}


@app.post("/api/wallet/topup")
def topup():
    con = db()
    con.execute("UPDATE users SET balance=balance+500000 WHERE id=?", (ME,))
    con.execute("INSERT INTO txns(user_id,amount,kind,day) VALUES(?,?,?,?)", (ME, 500_000, "topup", date.today().isoformat()))
    con.commit()
    return wallet()


@app.post("/api/rewards/{rid}/redeem")
def redeem(rid: str):
    con = db()
    r = next((r for r in REWARDS if r["id"] == rid), None)
    if not r:
        raise HTTPException(404, "not_found")
    if con.execute("UPDATE users SET points=points-? WHERE id=? AND points>=?", (r["cost"], ME, r["cost"])).rowcount == 0:
        raise HTTPException(400, "points")
    con.commit()
    return wallet()


@app.get("/api/community")
def community():
    con = db()
    users = {u["id"]: dict(u) for u in con.execute("SELECT id, name, name_en FROM users")}
    board = {}
    for p in active_pacts(con):
        b = board.setdefault(p["user_id"], {**users[p["user_id"]], "done": 0, "target": 0, "me": p["user_id"] == ME})
        b["done"] += min(p["done_days"], p["target_days"])
        b["target"] += p["target_days"]
    board = sorted(board.values(), key=lambda b: (-b["done"] / b["target"], -b["done"]))
    last = con.execute("SELECT * FROM settlements ORDER BY week DESC LIMIT 1").fetchone()
    return {"pool": pool_view(con), "leaderboard": board, "last": dict(last) if last else None,
            "week": week_start(date.today()).isoformat()}


@app.post("/api/settle")
def settle_week():
    """Demo: close the current week now (normally a Friday-night job)."""
    con = db()
    week = week_start(date.today()).isoformat()
    if con.execute("SELECT 1 FROM settlements WHERE week=?", (week,)).fetchone():
        raise HTTPException(409, "settled")
    pacts = active_pacts(con)
    deltas, fee, charity = settle(pacts)
    owner = {p["id"]: p["user_id"] for p in pacts}
    mine = 0
    for pid, amount in deltas.items():
        con.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, owner[pid]))
        con.execute("INSERT INTO txns(user_id,amount,kind,day) VALUES(?,?,?,?)",
                    (owner[pid], amount, "reward" if amount > 0 else "penalty", date.today().isoformat()))
        mine += amount if owner[pid] == ME else 0
    pool = sum(-v for v in deltas.values() if v < 0)
    con.execute("INSERT INTO settlements VALUES(?,?,?,?,?)", (week, pool, fee, charity, sum(v > 0 for v in deltas.values())))
    con.commit()
    return {"mine": mine, "pool": pool, "fee": fee, "charity": charity}


@app.get("/api/business")
def business():
    con = db()
    pacts = active_pacts(con)
    by_type = {}
    for p in pacts:
        t = by_type.setdefault(p["type"], [0, 0])
        t[0] += min(p["done_days"], p["target_days"])
        t[1] += p["target_days"]
    since = date.today() - timedelta(13)
    daily = dict(con.execute("SELECT day, COUNT(*) FROM checkins WHERE day>=? GROUP BY day", (since.isoformat(),)).fetchall())
    return {"members": len({p["user_id"] for p in pacts}), "pacts": len(pacts),
            "completion": {k: round(d / t, 3) for k, (d, t) in by_type.items()},
            "daily": [{"day": (since + timedelta(i)).isoformat(), "n": daily.get((since + timedelta(i)).isoformat(), 0)} for i in range(14)]}
