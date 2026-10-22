"""Phone + one-time-code login, sessions, and the signed-in user's own account."""
from __future__ import annotations

import hmac
import json
import logging
import re
import secrets
import time
import unicodedata
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import obs
from ..config import Settings
from ..db import db
from ..deps import Cfg, User, h
from ..security import client_ip

router = APIRouter(prefix="/api")

SESSION_TTL, OTP_TTL, OTP_TRIES, LOCK_SECS, DAILY_SENDS, MAX_SESSIONS = 30 * 86400, 120, 5, 900, 10, 5
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789", " -.()+\u200c\u00a0")  # Persian/Arabic digits to ASCII; separators deleted


def norm_phone(raw: str) -> str:
    """Accept Persian/Arabic digits, +98 / 0098 / 98 / 0 prefixes and space - . ( ) separators; return 09xxxxxxxxx or raise 400 'phone'."""
    m = re.fullmatch(r"(?:0098|98|0)?(9[0-9]{9})", raw.translate(DIGITS))  # [0-9] is ASCII only; str.isdigit() would accept other scripts
    if not m:
        raise HTTPException(400, "phone")
    return "0" + m[1]


def clean_name(raw: str) -> str:
    """Display names reach every leaderboard, so strip bidi/zero-width tricks. ZWNJ stays: Persian needs it."""
    s = unicodedata.normalize("NFKC", raw).strip()
    bad = any(unicodedata.category(c) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp") and c != "‌" for c in s)
    if not 1 <= len(s) <= 30 or bad:
        raise HTTPException(400, "name")
    return s


_sms = {"fails": 0, "until": 0.0}  # circuit breaker: after 3 straight provider failures, answer 503 for 60 s without calling it


def send_sms(st: Settings, phone: str, code: str):
    if st.sms_webhook_url:
        if time.monotonic() < _sms["until"]:
            raise HTTPException(503, "sms_unavailable")
        body = json.dumps({"phone": phone, "code": code, "text": f"کد تایید فیت‌پیمان: {code}"}).encode()
        req = urllib.request.Request(st.sms_webhook_url, body, {"content-type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5):  # nosec B310 nosemgrep: dynamic-urllib-use-detected - http(s) scheme enforced in Settings.from_env
                _sms["fails"] = 0
                return
        except urllib.error.HTTPError as e:
            if e.code < 500:  # the provider refused THIS number (invalid, blocked): a client problem, not an outage
                obs.event("sms_rejected", logging.WARNING, phone=obs.ref(phone), status=e.code)
                raise HTTPException(400, "phone") from e
            err = e
        except OSError as e:  # timeouts, DNS, refused connections
            err = e
        _sms["fails"] += 1
        if _sms["fails"] >= 3:
            _sms["until"] = time.monotonic() + 60
        obs.event("sms_failed", logging.ERROR, phone=obs.ref(phone), err=type(err).__name__, fails=_sms["fails"])
        raise HTTPException(503, "sms_unavailable") from err
    if not st.demo:
        raise HTTPException(503, "sms_unavailable")
    obs.event("demo_otp", phone=obs.ref(phone), code=code)


class PhoneIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)


class VerifyIn(PhoneIn):
    code: str = Field(min_length=6, max_length=6)


@router.post("/auth/otp")
def request_otp(body: PhoneIn, req: Request, st: Settings = Cfg):
    phone, ip, lim = norm_phone(body.phone), client_ip(req), req.app.state.limiter
    lim.check(("otp-ip", ip), 10, 600)
    lim.check(("otp", phone), 3, 600)
    code, now = f"{secrets.randbelow(10**6):06d}", int(time.time())
    with db(st.db_path, write=True) as con:
        o = con.execute("SELECT * FROM otps WHERE phone=?", (phone,)).fetchone()
        tries, sent, win = (o["tries"], o["sent"], o["win_start"]) if o else (0, 0, now)
        if o and o["locked_until"] > now:
            obs.event("otp_request_while_locked", logging.WARNING, phone=obs.ref(phone), ip=ip)
            raise HTTPException(429, "locked")
        if now - win > 86400:
            sent, win, tries = 0, now, 0  # the daily window also ages out old failed guesses
        if sent >= DAILY_SENDS:
            obs.event("otp_daily_cap", logging.WARNING, phone=obs.ref(phone), ip=ip)
            raise HTTPException(429, "rate_limited")
        # A resend never refills the guess counter: that is what stops "request new code, guess again" brute force.
        if o and o["locked_until"] and o["locked_until"] <= now:
            tries = 0
        con.execute("INSERT OR REPLACE INTO otps(phone,code_hash,expires,tries,locked_until,win_start,sent) VALUES(?,?,?,?,0,?,?)",
                    (phone, h(f"{phone}:{code}"), now + OTP_TTL, tries, win, sent + 1))
    try:
        lim.check(("sms-global",), st.sms_hourly_budget, 3600)  # SMS pumping costs real money: cap the whole app
        send_sms(st, phone, code)
    except HTTPException as e:
        if e.status_code == 503:  # a genuine outage: nothing was delivered, so it must not eat the budgets that gate everyone's login
            for k, per in ((("otp", phone), 600), (("sms-global",), 3600)):  # NOT the per-IP budget: one IP still cannot hammer the provider
                lim.refund(k, per)
        if e.status_code != 400:  # a number the provider rejected still counts against the phone and the IP
            with db(st.db_path, write=True) as con:
                con.execute("UPDATE otps SET sent=MAX(sent-1,0) WHERE phone=?", (phone,))
        raise
    obs.event("otp_sent", phone=obs.ref(phone), ip=ip)
    return {"ttl": OTP_TTL, **({"code": code} if st.demo else {})}


@router.post("/auth/verify")
def verify_otp(body: VerifyIn, req: Request, res: Response, st: Settings = Cfg):
    phone, code, now, ip, lim = norm_phone(body.phone), body.code.translate(DIGITS), int(time.time()), client_ip(req), req.app.state.limiter
    lim.check(("verify-ip", ip), 30, 600)
    lim.check(("verify", phone), 20, 600)
    token, new, fail = None, False, None
    with db(st.db_path, write=True) as con:
        o = con.execute("SELECT * FROM otps WHERE phone=?", (phone,)).fetchone()
        if not o or o["expires"] < now:
            fail = "code"
        elif o["locked_until"] > now:
            fail = "locked"
        elif not hmac.compare_digest(o["code_hash"], h(f"{phone}:{code}")):
            tries = o["tries"] + 1
            lock = now + LOCK_SECS if tries >= OTP_TRIES else 0
            con.execute("UPDATE otps SET tries=?, locked_until=? WHERE phone=?", (tries, lock, phone))
            fail = "code"
            if lock:
                obs.event("otp_locked", logging.WARNING, phone=obs.ref(phone), ip=ip)
        else:
            con.execute("UPDATE otps SET code_hash='', expires=0, tries=0 WHERE phone=?", (phone,))  # burn the code, keep the daily window
            u = con.execute("SELECT id FROM users WHERE phone=?", (phone,)).fetchone()
            new = u is None
            tag = secrets.randbelow(9000) + 1000  # public handle: never derived from the phone number
            uid = u["id"] if u else con.execute("INSERT INTO users(name,name_en,phone) VALUES(?,?,?)",
                                                (f"کاربر {tag}", f"User {tag}", phone)).lastrowid
            token = secrets.token_urlsafe(32)
            con.execute("INSERT INTO sessions VALUES(?,?,?)", (h(token), uid, now + SESSION_TTL))
            con.execute("""DELETE FROM sessions WHERE user_id=? AND token_hash NOT IN
                           (SELECT token_hash FROM sessions WHERE user_id=? ORDER BY expires DESC LIMIT ?)""", (uid, uid, MAX_SESSIONS))
    if fail:
        obs.event("login_failed", logging.WARNING, phone=obs.ref(phone), ip=ip, why=fail)
        raise HTTPException(429 if fail == "locked" else 400, fail)
    res.set_cookie(st.cookie_name, token, max_age=SESSION_TTL, httponly=True, secure=st.cookie_secure, samesite="strict", path="/")
    obs.event("login_ok", phone=obs.ref(phone), ip=ip, new=new)
    return {"new": new}


@router.post("/auth/logout")
def logout(req: Request, res: Response, st: Settings = Cfg):
    if tok := req.cookies.get(st.cookie_name):
        with db(st.db_path, write=True) as con:
            con.execute("DELETE FROM sessions WHERE token_hash=?", (h(tok),))
    res.delete_cookie(st.cookie_name, path="/", secure=st.cookie_secure, httponly=True, samesite="strict")
    return {"ok": True}


@router.post("/auth/logout-all")
def logout_all(res: Response, u: dict = User, st: Settings = Cfg):
    """Sign out of every device (a lost phone keeps a valid 30-day session until this runs)."""
    with db(st.db_path, write=True) as con:
        con.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
    obs.event("logout_all", user=u["id"])
    res.delete_cookie(st.cookie_name, path="/", secure=st.cookie_secure, httponly=True, samesite="strict")
    return {"ok": True}


def public_user(u: dict):
    return {k: u[k] for k in ("id", "name", "name_en", "balance", "points")}


@router.get("/me")
def me(u: dict = User, st: Settings = Cfg):
    return {**public_user(u), "phone": u["phone"], "demo": st.demo}


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


@router.patch("/me")
def rename(body: NameIn, u: dict = User, st: Settings = Cfg):
    name = clean_name(body.name)
    with db(st.db_path, write=True) as con:
        con.execute("UPDATE users SET name=?, name_en=? WHERE id=?", (name, name, u["id"]))
    return {**public_user(u), "name": name, "name_en": name}


@router.delete("/me")
def delete_account(res: Response, u: dict = User, st: Settings = Cfg):
    """Erasure: drops phone, sessions, pacts, check-ins and the OTP row; keeps only the anonymised ledger rows money movements need."""
    with db(st.db_path, write=True) as con:
        if con.execute("SELECT 1 FROM pacts WHERE user_id=? AND active=1", (u["id"],)).fetchone():
            raise HTTPException(409, "active_pacts")  # cancel first and wait for the week to close: no escaping a penalty
        if con.execute("SELECT balance FROM users WHERE id=?", (u["id"],)).fetchone()["balance"] > 0 and not st.demo:
            raise HTTPException(409, "has_balance")  # ponytail: needs the withdrawal flow before real money can leave
        con.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
        con.execute("DELETE FROM checkins WHERE pact_id IN (SELECT id FROM pacts WHERE user_id=?)", (u["id"],))  # self-written notes and the activity timeline
        con.execute("DELETE FROM pacts WHERE user_id=?", (u["id"],))
        con.execute("DELETE FROM otps WHERE phone=?", (u["phone"],))
        con.execute("UPDATE users SET phone=NULL, name='حذف‌شده', name_en='Deleted', points=0 WHERE id=?", (u["id"],))  # the ledger rows stay, anonymised
    obs.event("account_deleted", user=u["id"])
    res.delete_cookie(st.cookie_name, path="/", secure=st.cookie_secure, httponly=True, samesite="strict")
    return {"ok": True}
