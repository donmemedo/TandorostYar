"""Wallet, the (not yet redeemable) rewards list, and the demo-only top-up."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..config import Settings
from ..db import db
from ..deps import Cfg, User
from ..domain import today

router = APIRouter(prefix="/api")
REWARDS = [  # shown as "coming soon": there is deliberately no redeem endpoint until a partner can actually deliver
    {"id": "gym20", "cost": 300}, {"id": "coach", "cost": 500}, {"id": "bottle", "cost": 200}, {"id": "charity", "cost": 100}]


def wallet_view(con, uid, st: Settings):
    u = con.execute("SELECT balance, points FROM users WHERE id=?", (uid,)).fetchone()
    txns = con.execute("SELECT * FROM txns WHERE user_id=? ORDER BY id DESC LIMIT 30", (uid,)).fetchall()
    return {**dict(u), "txns": [dict(t) for t in txns], "rewards": REWARDS, "demo": st.demo}


@router.get("/wallet")
def wallet(u: dict = User, st: Settings = Cfg):
    with db(st.db_path) as con:
        return wallet_view(con, u["id"], st)


@router.post("/wallet/topup")
def topup(u: dict = User, st: Settings = Cfg):
    """Demo only: credits 500k with no payment. Real deposits must come from a signed payment-gateway callback."""
    if not st.demo:
        raise HTTPException(503, "topup_unavailable")
    with db(st.db_path, write=True) as con:
        con.execute("UPDATE users SET balance=balance+500000 WHERE id=?", (u["id"],))
        con.execute("INSERT INTO txns(user_id,amount,kind,day) VALUES(?,?,?,?)", (u["id"], 500_000, "topup", today(st.zone).isoformat()))
        return wallet_view(con, u["id"], st)
