"""Business rules and the SQL that feeds them. No HTTP in here."""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

FEE_PCT = 12  # service fee taken from the pool (business plan: 10-15%)
PAYOUT_CAP_X = 3  # OWNER DECISION: a winner never takes more than 3x their own exposure; the rest goes to charity
THRESHOLD = {"gym": 30, "nutrition": 3}  # per-day goal; steps uses pact.daily_goal
ROW_CAP = {"gym": 3, "steps": 20, "nutrition": 3}  # check-in rows per pact per day
VALUE_CAP = {"gym": 300, "steps": 40_000, "nutrition": 1}  # per row
DAY_CAP = {"gym": 600, "steps": 100_000, "nutrition": 3}  # plausible total per pact per day


def today(tz: ZoneInfo) -> date:
    return datetime.now(tz).date()


def week_start(d: date) -> date:  # Iranian week starts on Saturday
    return d - timedelta((d.weekday() - 5) % 7)


def settle(pacts, balances=None):
    """pacts: [{id, user_id, stake, target_days, done_days}] -> ({pact_id: delta}, fee, charity).

    Missed days cost `stake` each, but nobody pays more than their balance (balances: {user_id: int}).
    Winners split the pool minus fee by exposure (stake x target_days), capped at PAYOUT_CAP_X x their own exposure.
    Whatever is left, including the whole pool when nobody wins, goes to charity. Money is always conserved."""
    owed = {p["id"]: p["stake"] * (p["target_days"] - p["done_days"]) for p in pacts if p["done_days"] < p["target_days"]}
    if balances is not None:
        by_user: dict = {}
        for p in pacts:
            if p["id"] in owed:
                by_user.setdefault(p["user_id"], []).append(p["id"])
        for uid, ids in by_user.items():
            total, room = sum(owed[i] for i in ids), max(balances.get(uid, 0), 0)
            if total > room:
                for i in ids:
                    owed[i] = owed[i] * room // total
    pool = sum(owed.values())
    fee = pool * FEE_PCT // 100
    weight = {p["id"]: p["stake"] * p["target_days"] for p in pacts if p["done_days"] >= p["target_days"]}
    total_w = sum(weight.values())
    deltas = {i: -v for i, v in owed.items() if v}
    for i, w in weight.items():
        deltas[i] = min((pool - fee) * w // total_w, PAYOUT_CAP_X * w)
    charity = pool - fee - sum(v for v in deltas.values() if v > 0)
    return deltas, fee, charity


def done_days(con, start: date, end: date, user_id=None):
    """{pact_id: [days]} where each active pact met its daily threshold, for every pact in one query."""
    w, a = (" AND p.user_id=?", (user_id,)) if user_id else ("", ())
    out: dict = {}
    for r in con.execute(  # nosec B608 - `w` is a constant fragment, all values are bound
            f"""SELECT c.pact_id, c.day FROM checkins c JOIN pacts p ON p.id=c.pact_id WHERE p.active=1{w} AND c.day BETWEEN ? AND ?
                GROUP BY c.pact_id, c.day
                HAVING (CASE WHEN p.type='nutrition' THEN COUNT(*) ELSE SUM(c.value) END)
                    >= (CASE p.type WHEN 'steps' THEN p.daily_goal WHEN 'gym' THEN ? ELSE ? END)""",
            (*a, start.isoformat(), end.isoformat(), THRESHOLD["gym"], THRESHOLD["nutrition"])):
        out.setdefault(r["pact_id"], []).append(r["day"])
    return out


def pacts_view(con, start: date, end: date, day: date, user_id=None):
    """Active pacts with done days in [start, end] and progress on `day`. Three queries total, regardless of pact count."""
    w, a = (" AND p.user_id=?", (user_id,)) if user_id else ("", ())
    pacts = con.execute(f"SELECT * FROM pacts p WHERE p.active=1{w} ORDER BY p.id", a).fetchall()  # nosec B608
    done = done_days(con, start, end, user_id)
    now = dict(con.execute(  # nosec B608
        f"""SELECT c.pact_id, CASE WHEN p.type='nutrition' THEN COUNT(*) ELSE SUM(c.value) END FROM checkins c
            JOIN pacts p ON p.id=c.pact_id WHERE p.active=1{w} AND c.day=? GROUP BY c.pact_id""", (*a, day.isoformat())).fetchall())
    out = []
    for p in pacts:
        d = sorted(done.get(p["id"], []))
        goal = p["daily_goal"] if p["type"] == "steps" else THRESHOLD[p["type"]]
        out.append({**dict(p), "goal": goal, "today": now.get(p["id"], 0), "done_days": len(d), "days": d,
                    "at_risk": max(0, p["target_days"] - len(d)) * p["stake"]})
    return out


def streak(con, user_id, tod: date) -> int:
    days = {d for ds in done_days(con, tod - timedelta(400), tod, user_id).values() for d in ds}
    d, n = tod, 0
    if d.isoformat() not in days:
        d -= timedelta(1)
    while d.isoformat() in days:
        n, d = n + 1, d - timedelta(1)
    return n


def pool_view(pacts):
    deltas, fee, charity = settle(pacts)
    return {"amount": sum(-v for v in deltas.values() if v < 0), "fee": fee, "charity": charity, "fee_rate": FEE_PCT / 100,
            "participants": len({p["user_id"] for p in pacts}),
            "on_track": sum(p["done_days"] >= p["target_days"] for p in pacts), "pacts": len(pacts)}


# -- one shared, short-lived snapshot of everybody's pacts: dashboard pool, community board and the public business page
# all read it, so a burst of page loads costs one scan of the week's check-ins instead of one per request.
_snap: dict = {}
_snap_lock = threading.Lock()
SNAPSHOT_TTL = 5.0


def snapshot(con, key: str, start: date, tod: date):
    now = time.monotonic()
    with _snap_lock:
        hit = _snap.get((key, start, tod))
        if hit and now - hit[0] < SNAPSHOT_TTL:
            return hit[1]
    pacts = pacts_view(con, start, tod, tod)
    with _snap_lock:
        if len(_snap) > 64:
            _snap.clear()
        _snap[(key, start, tod)] = (now, pacts)
    return pacts


def invalidate():
    with _snap_lock:
        _snap.clear()


def settle_week(con, start: date, tod: date, end: date | None = None):
    """Settle the week beginning `start` (a Saturday) using check-ins through `end` (default: its Friday).
    Idempotent: the settlements primary key makes a second run a no-op. Returns the summary or None."""
    week, end = start.isoformat(), end or start + timedelta(6)
    if con.execute("SELECT 1 FROM settlements WHERE week=?", (week,)).fetchone():
        return None
    pacts = [p for p in pacts_view(con, start, end, end) if (p["created"] or week) <= end.isoformat()]
    if not pacts:
        return None
    balances = {r["id"]: r["balance"] for r in con.execute("SELECT id, balance FROM users WHERE id IN (SELECT user_id FROM pacts WHERE active=1)")}
    deltas, fee, charity = settle(pacts, balances)
    owner = {p["id"]: p["user_id"] for p in pacts}
    for pid, amount in deltas.items():
        if amount:
            con.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, owner[pid]))
            con.execute("INSERT INTO txns(user_id,amount,kind,day) VALUES(?,?,?,?)", (owner[pid], amount, "reward" if amount > 0 else "penalty", tod.isoformat()))
    pool = sum(-v for v in deltas.values() if v < 0)
    con.execute("INSERT INTO settlements VALUES(?,?,?,?,?)", (week, pool, fee, charity, sum(v > 0 for v in deltas.values())))
    # Pacts a user cancelled end now; pacts a user can no longer cover are paused, so balances never go negative.
    con.execute("UPDATE pacts SET active=0 WHERE active=1 AND ends IS NOT NULL AND ends<=?", (end.isoformat(),))
    con.execute("""UPDATE pacts SET active=0 WHERE active=1 AND user_id IN (
                   SELECT u.id FROM users u JOIN pacts p ON p.user_id=u.id AND p.active=1
                   GROUP BY u.id HAVING u.balance < SUM(p.stake*p.target_days))""")
    invalidate()
    return {"week": week, "pool": pool, "fee": fee, "charity": charity, "deltas": deltas, "owner": owner}


def settle_due(con, tod: date):
    """Settle every completed, unsettled week since the ledger epoch (at most the last four). Safe to call any time."""
    epoch = con.execute("SELECT v FROM meta WHERE k='epoch'").fetchone()
    first = date.fromisoformat(epoch["v"]) if epoch else week_start(tod)
    done = []
    for back in range(4, 0, -1):
        start = week_start(tod) - timedelta(7 * back)
        if start >= first and (r := settle_week(con, start, tod)):
            done.append(r)
    return done
