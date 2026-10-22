"""Community board, the public business aggregates, and settlement triggers."""
from __future__ import annotations

import hmac
import json
import logging
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request

from .. import obs
from ..config import Settings
from ..db import db
from ..deps import Cfg, User
from ..domain import daily_checkins, pool_view, settle_due, settle_week, snapshot, today, week_start
from ..security import client_ip

router = APIRouter(prefix="/api")
BOARD = 50


@router.get("/community")
def community(u: dict = User, st: Settings = Cfg):
    tod = today(st.zone)
    start = week_start(tod)
    with db(st.db_path) as con:
        pacts = snapshot(con, st.db_path, start, tod)
        ids = sorted({p["user_id"] for p in pacts})
        users = {r["id"]: dict(r) for r in con.execute("SELECT id, name, name_en FROM users WHERE id IN (SELECT value FROM json_each(?))", (json.dumps(ids),))}  # the snapshot's users, even if a settlement just paused them
        last = con.execute("SELECT * FROM settlements ORDER BY week DESC LIMIT 1").fetchone()
    board: dict = {}
    for p in pacts:
        b = board.setdefault(p["user_id"], {**users[p["user_id"]], "done": 0, "target": 0, "me": p["user_id"] == u["id"]})
        b["done"] += min(p["done_days"], p["target_days"])
        b["target"] += p["target_days"]
    rows = sorted(board.values(), key=lambda b: (-b["done"] / b["target"], -b["done"]))
    top = rows[:BOARD] + [r for r in rows[BOARD:] if r["me"]]
    return {"pool": pool_view(pacts), "leaderboard": top, "members": len(ids), "last": dict(last) if last else None,
            "week": start.isoformat(), "demo": st.demo}


@router.post("/settle")
def settle_now(u: dict = User, st: Settings = Cfg):
    """Demo only: close the current week today, counting the remaining days as missed."""
    if not st.demo:
        raise HTTPException(404, "not_found")
    with db(st.db_path, write=True) as con:
        tod = today(st.zone)
        r = settle_week(con, week_start(tod), tod, tod)
    if not r:
        raise HTTPException(409, "settled")
    mine = sum(a for pid, a in r["deltas"].items() if r["owner"][pid] == u["id"])
    return {"mine": mine, "pool": r["pool"], "fee": r["fee"], "charity": r["charity"]}


@router.post("/admin/settle")
def admin_settle(req: Request, st: Settings = Cfg):
    """Operator trigger for the weekly settlement (the in-process scheduler runs the same code every 10 minutes)."""
    given = req.headers.get("authorization", "").removeprefix("Bearer ").strip().encode()
    if not st.admin_token or not hmac.compare_digest(given, st.admin_token.encode()):  # bytes: non-ASCII input must not raise
        obs.event("admin_denied", logging.WARNING, ip=client_ip(req))
        raise HTTPException(404, "not_found")
    with db(st.db_path, write=True) as con:
        con.execute("DELETE FROM meta WHERE k='held'")  # an operator decision releases a settlement hold (see main.sweep)
        settle_due(con, today(st.zone))
    obs.event("admin_settle", ip=client_ip(req))
    with db(st.db_path) as con:
        return [dict(r) for r in con.execute("SELECT * FROM settlements ORDER BY week DESC LIMIT 5")]


@router.get("/business")
def business(st: Settings = Cfg):
    """Public aggregates for the B2B page: no names, no per-user data, served from the shared snapshot."""
    tod = today(st.zone)
    start = week_start(tod)
    since = tod - timedelta(13)
    with db(st.db_path) as con:
        pacts = snapshot(con, st.db_path, start, tod)
        daily = daily_checkins(con, st.db_path, since)
    by_type: dict = {}
    for p in pacts:
        t = by_type.setdefault(p["type"], [0, 0])
        t[0] += min(p["done_days"], p["target_days"])
        t[1] += p["target_days"]
    return {"members": len({p["user_id"] for p in pacts}), "pacts": len(pacts),
            "completion": {k: round(d / t, 3) for k, (d, t) in by_type.items()},
            "daily": [{"day": (since + timedelta(i)).isoformat(), "n": daily.get((since + timedelta(i)).isoformat(), 0)} for i in range(14)]}
