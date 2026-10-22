"""Pacts and check-ins."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field, field_validator

from .. import obs
from ..config import Settings
from ..db import db
from ..deps import Cfg, User
from ..domain import DAY_CAP, ROW_CAP, THRESHOLD, VALUE_CAP, pacts_view, pool_view, is_held, settle_due, snapshot, streak, today, week_start
from .auth import public_user

router = APIRouter(prefix="/api")


@router.get("/health")
def health(st: Settings = Cfg):
    with db(st.db_path) as con:
        last = con.execute("SELECT MAX(week) AS w FROM settlements").fetchone()["w"]
    return {"ok": True, "settled_through": last}  # monitor this: it should always be last week's Saturday or later


@router.get("/dashboard")
def dashboard(u: dict = User, st: Settings = Cfg):
    tod = today(st.zone)
    start = week_start(tod)
    with db(st.db_path) as con:
        mine = pacts_view(con, start, tod, tod, u["id"])  # fresh: you must see your own check-in immediately
        everyone = snapshot(con, st.db_path, start, tod)  # shared 5-second snapshot: the pool is not personal
        s = streak(con, u["id"], tod)
        paused = not mine and con.execute("SELECT 1 FROM txns WHERE user_id=? AND kind='paused' AND day>=?", (u["id"], (tod - timedelta(8)).isoformat())).fetchone() is not None
    return {"user": {**public_user(u), "streak": s}, "pacts": mine, "pool": pool_view(everyone), "demo": st.demo, "paused": paused,
            "week": [(start + timedelta(i)).isoformat() for i in range(7)], "today": tod.isoformat(), "days_left": 7 - (tod - start).days}


class NewPact(BaseModel):
    type: Literal["gym", "steps", "nutrition"]
    target_days: int = Field(ge=1, le=7)
    stake: int = Field(ge=0, le=1_000_000)  # 0 = a no-money pact: points and a streak only (the only kind possible before payments exist)
    daily_goal: int | None = Field(None, ge=6000, le=40_000)  # the UI's lowest option: a trivially easy goal is a free claim on the pool

    @field_validator("stake")
    @classmethod
    def _stake(cls, v: int) -> int:
        if 0 < v < 10_000:
            raise ValueError("stake")
        return v


@router.post("/pacts")
def create_pact(body: NewPact, u: dict = User, st: Settings = Cfg):
    with db(st.db_path, write=True) as con:
        tod = today(st.zone)  # evaluated under the write lock, once
        start = week_start(tod)
        if is_held(con):
            raise HTTPException(503, "held")  # fail closed: no new money commitments while the server clock is under suspicion
        settle_due(con, tod)  # a week that just ended settles BEFORE we judge affordability, never in the middle of this request
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
        goal = (body.daily_goal or THRESHOLD["steps"]) if body.type == "steps" else THRESHOLD[body.type]  # the pact's terms are fixed now
        pid = con.execute("INSERT INTO pacts(user_id,type,target_days,stake,daily_goal,created) VALUES(?,?,?,?,?,?)",
                          (u["id"], body.type, body.target_days, body.stake, goal, tod.isoformat())).lastrowid
        out = next(p for p in pacts_view(con, start, tod, tod, u["id"]) if p["id"] == pid)
    obs.event("pact_created", user=u["id"], type=body.type, days=body.target_days, stake=body.stake)
    return out


@router.delete("/pacts/{pid}")
def end_pact(pid: Annotated[int, Path(ge=1, le=2**63 - 1)], u: dict = User, st: Settings = Cfg):
    """Cancelling takes effect when the current week closes, so it cannot be used to dodge this week's penalty."""
    with db(st.db_path, write=True) as con:
        end = week_start(today(st.zone)) + timedelta(6)
        if con.execute("UPDATE pacts SET ends=? WHERE id=? AND user_id=? AND active=1", (end.isoformat(), pid, u["id"])).rowcount == 0:
            raise HTTPException(404, "not_found")
    return {"ends": end.isoformat()}


class CheckIn(BaseModel):
    value: int = Field(ge=1, le=100_000)  # minutes, steps; meals always count as 1. No free text: nothing here is ever read back, so it is not stored


@router.post("/pacts/{pid}/checkin")
def checkin(pid: Annotated[int, Path(ge=1, le=2**63 - 1)], body: CheckIn, u: dict = User, st: Settings = Cfg):
    with db(st.db_path, write=True) as con:
        tod = today(st.zone)
        start = week_start(tod)
        p = con.execute("SELECT * FROM pacts WHERE id=? AND user_id=? AND active=1", (pid, u["id"])).fetchone()
        if is_held(con):
            raise HTTPException(503, "held")  # check-ins are attributed to a day by the clock, so they stop too while it is suspect
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
        con.execute("INSERT INTO checkins(pact_id,day,value) VALUES(?,?,?)", (pid, tod.isoformat(), value))
        if total < p["daily_goal"] <= total + value:  # this check-in crossed today's goal
            con.execute("UPDATE users SET points=points+10 WHERE id=?", (u["id"],))
        after = next(v for v in pacts_view(con, start, tod, tod, u["id"]) if v["id"] == pid)
    return after
