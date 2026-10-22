from __future__ import annotations

import hashlib
import time

from fastapi import Depends, HTTPException, Request

from .config import Settings
from .db import db


def h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def get_settings(req: Request) -> Settings:
    return req.app.state.settings


def current_user(req: Request, st: Settings = Depends(get_settings)) -> dict:
    tok = req.cookies.get(st.cookie_name)
    if not tok:
        raise HTTPException(401, "auth")
    with db(st.db_path) as con:
        u = con.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?",
                        (h(tok), int(time.time()))).fetchone()
    if not u:
        raise HTTPException(401, "auth")
    return dict(u)


User = Depends(current_user)
Cfg = Depends(get_settings)
