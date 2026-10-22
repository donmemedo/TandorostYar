"""FitPeyman API. Run with:  uvicorn app.main:create_app --factory"""
from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import obs
from .config import Settings
from .db import db, init
from .domain import settle_due, today
from .routes import auth, community, pacts, wallet
from .security import Guards, Limiter

SWEEP_SECS = 600


def sweep(st: Settings, jumped: bool = False):
    """Background housekeeping: settle finished weeks, drop expired one-time codes and sessions.
    Settlement trusts the wall clock, so if the clock moved (backwards, or a sudden jump in-process) it HOLDS and shouts instead of
    charging people on a bad date. An operator releases the hold with POST /api/admin/settle."""
    now = int(time.time())
    with db(st.db_path, write=True) as con:
        last = con.execute("SELECT v FROM meta WHERE k='last_sweep'").fetchone()
        if not con.execute("SELECT 1 FROM meta WHERE k='held'").fetchone() and (jumped or (last and now < int(last["v"]) - 60)):
            reason = "clock jumped in-process" if jumped else f"clock moved back {int(last['v']) - now}s"
            con.execute("INSERT OR REPLACE INTO meta VALUES('held', ?)", (reason,))
        if held := con.execute("SELECT v FROM meta WHERE k='held'").fetchone():
            obs.event("settlement_held", logging.CRITICAL, reason=held["v"], hint="verify the server clock, then POST /api/admin/settle")
        else:
            settle_due(con, today(st.zone))
        con.execute("INSERT OR REPLACE INTO meta VALUES('last_sweep', ?)", (str(now),))
        con.execute("DELETE FROM otps WHERE expires<? AND locked_until<? AND win_start<?", (now, now, now - 86400))  # keep the 24 h send window
        con.execute("DELETE FROM sessions WHERE expires<?", (now,))
        bad = con.execute("SELECT COUNT(*) FROM users u WHERE u.balance != COALESCE((SELECT SUM(amount) FROM txns WHERE user_id=u.id), 0)").fetchone()[0]
    if bad:  # every balance must equal the sum of its ledger rows; anything else is a bug or tampering
        obs.event("ledger_mismatch", logging.CRITICAL, users=bad)


def scheduler(st: Settings, stop: threading.Event):  # ponytail: in-process timer; move to cron/systemd if you run >1 replica
    w0, m0, seen = time.time(), time.monotonic(), 0.0
    while True:
        drift = (time.time() - w0) - (time.monotonic() - m0)  # wall clock vs a clock that cannot be set
        jumped, seen = abs(drift - seen) > 600, drift
        try:
            sweep(st, jumped)
        except Exception:
            obs.log.exception("sweep_failed")
        if stop.wait(SWEEP_SECS):
            return


def create_app(st: Settings | None = None) -> FastAPI:
    st = st or Settings.from_env()
    obs.configure(st.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init(st)
        if st.demo:
            obs.event("demo_mode_on", logging.CRITICAL, note="OTP codes are returned in responses. Never run this in production.")
        if not st.demo and not st.cookie_secure:
            obs.event("insecure_cookies", logging.CRITICAL, note="COOKIE_SECURE is off outside DEMO: sessions travel without the Secure and __Host- protections.")
        if not st.demo and not os.getenv("LOG_KEY"):
            obs.event("log_key_unset", logging.WARNING, note="Set LOG_KEY (32+ chars) so phone references in logs stay comparable across restarts.")
        stop = threading.Event()
        t = threading.Thread(target=scheduler, args=(st, stop), daemon=True, name="sweeper")
        t.start()
        yield
        stop.set()
        t.join(timeout=5)

    app = FastAPI(title="FitPeyman API", lifespan=lifespan, docs_url="/api/docs" if st.demo else None, redoc_url=None,
                  openapi_url="/api/openapi.json" if st.demo else None)
    limiter = Limiter()
    app.state.settings, app.state.limiter = st, limiter
    app.add_middleware(Guards, st=st, limiter=limiter)  # added last = outermost: rejects before any other work happens

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, exc: RequestValidationError):  # never echo the submitted input back
        return JSONResponse({"detail": "invalid"}, 422)

    @app.exception_handler(Exception)
    async def boom(_: Request, exc: Exception):
        obs.log.error("unhandled", exc_info=exc)
        return JSONResponse({"detail": "server"}, 500)

    for r in (auth.router, pacts.router, wallet.router, community.router):
        app.include_router(r)
    return app
