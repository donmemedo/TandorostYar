"""Business rules and the SQL that feeds them. No HTTP in here."""
from __future__ import annotations

import os
import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import obs

FEE_PCT = 12  # service fee taken from the pool (business plan: 10-15%)
PAYOUT_CAP_X = int(os.getenv("PAYOUT_CAP_X", "3"))  # OWNER DECISION: a winner never takes more than N x own exposure; the rest goes to charity.
# PAYOUT_CAP_X=0 is "charity-only" mode: nobody is ever paid from another user's stake (see docs/ROADMAP.md, legal gate).
THRESHOLD = {"gym": 30, "nutrition": 3, "steps": 8000}  # default per-day goal; copied onto each pact at creation, so its terms never change
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
        deltas[i] = min((pool - fee) * w // total_w, PAYOUT_CAP_X * w) if total_w else 0  # total_w is 0 when every winner staked nothing
    charity = pool - fee - sum(v for v in deltas.values() if v > 0)
    return deltas, fee, charity


def done_days(con, start: date, end: date, user_id=None):
    """{pact_id: [days]} where each active pact met its daily threshold, for every pact in one query."""
    w, a = (" AND p.user_id=?", (user_id,)) if user_id else ("", ())
    out: dict = {}
    for r in con.execute(
            f"""SELECT c.pact_id, c.day FROM checkins c JOIN pacts p ON p.id=c.pact_id WHERE p.active=1{w} AND c.day BETWEEN ? AND ?
                GROUP BY c.pact_id, c.day HAVING SUM(c.value) >= p.daily_goal""",  # nosec B608 - `w` is a constant fragment, every value is bound
            (*a, start.isoformat(), end.isoformat())):
        out.setdefault(r["pact_id"], []).append(r["day"])
    return out


def pacts_view(con, start: date, end: date, day: date, user_id=None):
    """Active pacts with done days in [start, end] and progress on `day`. Three queries total, regardless of pact count."""
    w, a = (" AND p.user_id=?", (user_id,)) if user_id else ("", ())
    pacts = con.execute(f"SELECT * FROM pacts p WHERE p.active=1{w} ORDER BY p.id", a).fetchall()  # nosec B608
    done = done_days(con, start, end, user_id)
    now = dict(con.execute(
        f"""SELECT c.pact_id, SUM(c.value) FROM checkins c
            JOIN pacts p ON p.id=c.pact_id WHERE p.active=1{w} AND c.day=? GROUP BY c.pact_id""",  # nosec B608 - constant fragment
        (*a, day.isoformat())).fetchall())
    out = []
    for p in pacts:
        d = sorted(done.get(p["id"], []))
        out.append({**dict(p), "goal": p["daily_goal"], "today": now.get(p["id"], 0), "done_days": len(d), "days": d,
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


# -- one shared, short-lived cache for what every page needs about everybody (the pool, the board, the public chart), so a burst
# of page loads costs one scan of the week's check-ins instead of one per request. TTL-only on purpose: invalidating on every
# write would turn heavy write traffic into a recompute storm. Single flight: when an entry expires, one thread recomputes and
# the rest reuse the result. Your OWN data is never read from here.
_cache: dict = {}
_cache_lock = threading.Lock()
SNAPSHOT_TTL = 5.0


def _cached(key, compute):
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < SNAPSHOT_TTL:
        return hit[1]
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < SNAPSHOT_TTL:
            return hit[1]
        value = compute()
        if len(_cache) > 64:
            _cache.clear()
        _cache[key] = (time.monotonic(), value)
        return value


def snapshot(con, key: str, start: date, tod: date):
    return _cached(("pacts", key, start, tod), lambda: pacts_view(con, start, tod, tod))


def daily_checkins(con, key: str, since: date):
    return _cached(("daily", key, since), lambda: dict(con.execute("SELECT day, COUNT(*) FROM checkins WHERE day>=? GROUP BY day", (since.isoformat(),)).fetchall()))


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
    con.execute("UPDATE pacts SET active=0 WHERE active=1 AND ends IS NOT NULL AND ends<=?", ((start + timedelta(6)).isoformat(),))  # the week's Friday, even when closed early
    short = [r["id"] for r in con.execute("""SELECT u.id FROM users u JOIN pacts p ON p.user_id=u.id AND p.active=1
                                              GROUP BY u.id HAVING u.balance < SUM(p.stake*p.target_days)""")]
    for uid in short:  # tell the user, not just the database: a zero-amount ledger row that the wallet and dashboard surface
        con.execute("UPDATE pacts SET active=0, ends=COALESCE(ends, ?) WHERE active=1 AND user_id=?", ((start + timedelta(6)).isoformat(), uid))
        con.execute("INSERT INTO txns(user_id,amount,kind,day) VALUES(?,?,?,?)", (uid, 0, "paused", tod.isoformat()))
    _cache.clear()  # a settled week changes everyone's pacts: do not serve the old snapshot
    obs.event("week_settled", week=week, pool=pool, fee=fee, charity=charity, winners=sum(v > 0 for v in deltas.values()), paused=len(short))
    return {"week": week, "pool": pool, "fee": fee, "charity": charity, "deltas": deltas, "owner": owner}


def is_held(con) -> bool:
    """True while the clock-safety hold is on (see main.sweep)."""
    return con.execute("SELECT 1 FROM meta WHERE k='held'").fetchone() is not None


def settle_due(con, tod: date):
    """Settle every completed, unsettled week since the ledger epoch (at most the last four). Safe to call any time.
    Does nothing while the clock-safety hold is on, no matter who calls it (sweeper, create_pact, admin after it clears the hold)."""
    if is_held(con):
        return []
    epoch = con.execute("SELECT v FROM meta WHERE k='epoch'").fetchone()
    first = date.fromisoformat(epoch["v"]) if epoch else week_start(tod)
    done = []
    for back in range(4, 0, -1):
        start = week_start(tod) - timedelta(7 * back)
        if start < first:
            continue
        if r := settle_week(con, start, tod):
            done.append(r)
        else:  # no pacts that week: record it, so it is not recomputed every sweep and history has no holes
            con.execute("INSERT OR IGNORE INTO settlements VALUES(?,0,0,0,0)", (start.isoformat(),))
    return done
