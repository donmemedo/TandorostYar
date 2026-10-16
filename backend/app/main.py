"""FitPeyman API. Run with:  uvicorn app.main:create_app --factory"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from . import obs
from .config import Settings
from .db import db, init
from .domain import settle_due, today
from .routes import auth, community, pacts, wallet
from .security import Guards, Limiter

SWEEP_SECS = 600


def sweep(st: Settings):
    """Background housekeeping: settle finished weeks, drop expired one-time codes and sessions."""
    with db(st.db_path, write=True) as con:
        for r in settle_due(con, today(st.zone)):
            obs.event("week_settled", week=r["week"], pool=r["pool"], fee=r["fee"], charity=r["charity"], winners=sum(v > 0 for v in r["deltas"].values()))
        now = int(time.time())
        con.execute("DELETE FROM otps WHERE expires<? AND locked_until<?", (now, now))
        con.execute("DELETE FROM sessions WHERE expires<?", (now,))


def scheduler(st: Settings, stop: threading.Event):  # ponytail: in-process timer; move to cron/systemd if you run >1 replica
    while True:
        try:
            sweep(st)
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
    app.add_middleware(GZipMiddleware, minimum_size=1000)
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
