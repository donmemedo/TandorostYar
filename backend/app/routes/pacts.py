"""Pacts and check-ins."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import obs
from ..config import Settings
from ..db import db
from ..deps import Cfg, User
from ..domain import DAY_CAP, ROW_CAP, VALUE_CAP, invalidate, pacts_view, pool_view, snapshot, streak, today, week_start
from .auth import public_user

router = APIRouter(prefix="/api")


@router.get("/health")
def health(st: Settings = Cfg):
    with db(st.db_path) as con:
        con.execute("SELECT 1").fetchone()
    return {"ok": True}


@router.get("/dashboard")
def dashboard(u: dict = User, st: Settings = Cfg):
    tod = today(st.zone)
    start = week_start(tod)
    with db(st.db_path) as con:
        mine = pacts_view(con, start, tod, tod, u["id"])  # fresh: you must see your own check-in immediately
        everyone = snapshot(con, st.db_path, start, tod)  # shared 5-second snapshot: the pool is not personal
        s = streak(con, u["id"], tod)
    return {"user": {**public_user(u), "streak": s}, "pacts": mine, "pool": pool_view(everyone), "demo": st.demo,
            "week": [(start + timedelta(i)).isoformat() for i in range(7)], "today": tod.isoformat(), "days_left": 7 - (tod - start).days}


class NewPact(BaseModel):
    type: Literal["gym", "steps", "nutrition"]
    target_days: int = Field(ge=1, le=7)
    stake: int = Field(ge=10_000, le=1_000_000)
    daily_goal: int | None = Field(None, ge=1000, le=40_000)


@router.post("/pacts")
def create_pact(body: NewPact, u: dict = User, st: Settings = Cfg):
    with db(st.db_path, write=True) as con:
        tod = today(st.zone)  # evaluated under the write lock, once
        start = week_start(tod)
        if body.target_days > 7 - (tod - start).days:
            raise HTTPException(400, "days")  # cannot promise more days than are left in this week
        if con.execute("SELECT 1 FROM settlements WHERE week=?", (start.isoformat(),)).fetchone():
            raise HTTPException(409, "settled")
        mine = pacts_view(con, start, tod, tod, u["id"])
        if any(p["type"] == body.type for p in mine):
            raise HTTPException(409, "exists")
        balance = con.execute("SELECT balance FROM users WHERE id=?", (u["id"],)).fetchone()["balance"]  # fresh, under the lock
        held = sum(p["target_days"] * p["stake"] for p in mine)  # money already pledged
        if balance - held < body.stake * body.target_days:
            raise HTTPException(400, "balance")
        goal = (body.daily_goal or 8000) if body.type == "steps" else None
        pid = con.execute("INSERT INTO pacts(user_id,type,target_days,stake,daily_goal,created) VALUES(?,?,?,?,?,?)",
                          (u["id"], body.type, body.target_days, body.stake, goal, tod.isoformat())).lastrowid
        out = next(p for p in pacts_view(con, start, tod, tod, u["id"]) if p["id"] == pid)
    invalidate()
    obs.event("pact_created", user=u["id"], type=body.type, days=body.target_days, stake=body.stake)
    return out


@router.delete("/pacts/{pid}")
def end_pact(pid: int, u: dict = User, st: Settings = Cfg):
    """Cancelling takes effect when the current week closes, so it cannot be used to dodge this week's penalty."""
    with db(st.db_path, write=True) as con:
        end = week_start(today(st.zone)) + timedelta(6)
        if con.execute("UPDATE pacts SET ends=? WHERE id=? AND user_id=? AND active=1", (end.isoformat(), pid, u["id"])).rowcount == 0:
            raise HTTPException(404, "not_found")
    invalidate()
    return {"ends": end.isoformat()}


class CheckIn(BaseModel):
    value: int = Field(ge=1, le=100_000)
    note: str | None = Field(None, max_length=60)


@router.post("/pacts/{pid}/checkin")
def checkin(pid: int, body: CheckIn, u: dict = User, st: Settings = Cfg):
    with db(st.db_path, write=True) as con:
        tod = today(st.zone)
        start = week_start(tod)
        p = con.execute("SELECT * FROM pacts WHERE id=? AND user_id=? AND active=1", (pid, u["id"])).fetchone()
        if not p:
            raise HTTPException(404, "not_found")  # also the answer for someone else's pact: no existence oracle
        if con.execute("SELECT 1 FROM settlements WHERE week=?", (start.isoformat(),)).fetchone():
            raise HTTPException(409, "settled")  # a closed week is immutable
        value = 1 if p["type"] == "nutrition" else body.value
        if value > VALUE_CAP[p["type"]]:
            raise HTTPException(400, "value")
        n, total = con.execute("SELECT COUNT(*), COALESCE(SUM(value),0) FROM checkins WHERE pact_id=? AND day=?", (pid, tod.isoformat())).fetchone()
        if n >= ROW_CAP[p["type"]] or total + value > DAY_CAP[p["type"]]:
            raise HTTPException(429, "limit")
        before = next(v for v in pacts_view(con, start, tod, tod, u["id"]) if v["id"] == pid)
        con.execute("INSERT INTO checkins(pact_id,day,value,note) VALUES(?,?,?,?)", (pid, tod.isoformat(), value, body.note))
        after = next(v for v in pacts_view(con, start, tod, tod, u["id"]) if v["id"] == pid)
        if after["done_days"] > before["done_days"]:  # crossed today's goal
            con.execute("UPDATE users SET points=points+10 WHERE id=?", (u["id"],))
    invalidate()
    return after
