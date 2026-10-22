"""Rate limiting, client-IP resolution and the ASGI guard that fronts every request."""
from __future__ import annotations

import ipaddress
import re
import secrets
import threading
import time

from fastapi import HTTPException, Request

from . import obs
from .config import Settings

MAX_BODY = 16 * 1024
SAFE = {b"GET", b"HEAD", b"OPTIONS"}
RID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


class Limiter:
    """Fixed-window counters. Memory is bounded: expired windows are dropped when the table fills and, if an attacker
    still fills it with live keys, NEW keys are refused (fail closed) instead of wiping everyone's counters.
    ponytail: single-process memory; move to Redis if you ever run more than one worker."""

    FULL = 10**9  # returned by bump() when the table is full of live keys

    def __init__(self, cap: int = 100_000, clock=time.time):
        self._clock = clock
        self._h: dict[tuple, list] = {}
        self._lock = threading.Lock()
        self._cap = cap

    def bump(self, key, per: int) -> int:
        """Count one hit for `key` in the current window and return the new count."""
        now = self._clock()
        win, k = int(now // per), (key, per)
        with self._lock:
            e = self._h.get(k)
            if e is None:
                if len(self._h) >= self._cap:
                    self._h = {kk: v for kk, v in self._h.items() if (v[0] + 1) * kk[1] > now}
                    if len(self._h) >= self._cap:
                        return self.FULL
                e = self._h[k] = [win, 0]
            elif e[0] != win:
                e[0], e[1] = win, 0
            e[1] += 1
            return e[1]

    def hit(self, key, n: int, per: int) -> bool:
        return self.bump(key, per) <= n

    def refund(self, key, per: int):
        """Give back one hit (used when the thing the hit paid for never happened, e.g. the SMS was not sent)."""
        with self._lock:
            e = self._h.get((key, per))
            if e and e[0] == int(self._clock() // per) and e[1] > 0:
                e[1] -= 1

    def check(self, key, n: int, per: int):
        c = self.bump(key, per)
        if c > n:
            if c in (n + 1, self.FULL):  # log the first rejection per window only: a flood must not flood the logs
                obs.event("rate_limited", 30, scope=key[0] if isinstance(key, tuple) else key)  # scope only: never the phone number
            raise HTTPException(429, "rate_limited", headers={"Retry-After": str(per)})


def _net(a: str):
    """One key per client: IPv4-mapped IPv6 collapses to IPv4, and a whole IPv6 /64 (one subscriber, 2^64 addresses) counts as one."""
    ip = ipaddress.ip_address(a)
    if ip.version == 6 and ip.ipv4_mapped:
        return str(ip.ipv4_mapped)
    return str(ipaddress.ip_network(f"{ip}/64", strict=False).network_address) + "/64" if ip.version == 6 else str(ip)


def peer_ip(scope: dict, hops: int) -> str:
    """Socket peer, or the Nth-from-right X-Forwarded-For entry when `hops` trusted proxies append to it.
    The leftmost entry is client-controlled and is never believed."""
    peer = (scope.get("client") or ("?", 0))[0]
    if hops:
        for k, v in scope["headers"]:
            if k == b"x-forwarded-for":
                parts = [p.strip() for p in v.decode("latin-1").split(",")]
                if len(parts) >= hops:
                    try:
                        return _net(parts[-hops])
                    except ValueError:
                        pass
    try:
        return _net(peer)
    except ValueError:
        return peer


def _json(status: int, detail: str, extra: list | None = None) -> tuple[list, bytes]:
    body = ('{"detail":"%s"}' % detail).encode()
    return [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *(extra or [])], body


class Guards:
    """Pure ASGI (no per-request task like BaseHTTPMiddleware). Enforces, for every /api request:
    streaming body cap, CSRF, per-IP rate limit; then stamps security headers, request id, Server-Timing and an access log."""

    def __init__(self, app, st: Settings, limiter: Limiter):
        self.app, self.st, self.limiter = app, st, limiter

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        t0 = time.perf_counter()
        h = dict(scope["headers"])
        rid = (h.get(b"x-request-id") or b"").decode("latin-1")
        rid = rid if RID.match(rid) else secrets.token_hex(8)
        obs.rid_var.set(rid)
        ip = peer_ip(scope, self.st.proxy_hops)
        scope.setdefault("state", {})["ip"] = ip
        api, method, status = scope["path"].startswith("/api/"), scope["method"].encode(), 0

        async def respond(code: int, detail: str, extra=None):
            hdrs, body = _json(code, detail, extra)
            await wrapped_send({"type": "http.response.start", "status": code, "headers": hdrs})
            await wrapped_send({"type": "http.response.body", "body": body})

        async def wrapped_send(msg):
            nonlocal status
            if msg["type"] == "http.response.start":
                status = msg["status"]
                out = [(k, v) for k, v in msg["headers"] if k not in (b"server", b"x-powered-by")]
                out += [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer"),
                        (b"x-request-id", rid.encode()), (b"cross-origin-resource-policy", b"same-origin"),
                        (b"server-timing", b"app;dur=%.1f" % ((time.perf_counter() - t0) * 1000))]
                if api:
                    out += [(b"cache-control", b"no-store"), (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")]
                msg = {**msg, "headers": out}
            await send(msg)

        if api:
            # The limiter runs FIRST so that rejected requests spend budget too (a stream of cheap 403s/413s cannot be free).
            c = self.limiter.bump(("ip", ip), 60)
            if c > self.st.rate_per_min:
                if c in (self.st.rate_per_min + 1, self.limiter.FULL):
                    obs.event("rate_limited", 30, ip=ip, scope="global")
                return await respond(429, "rate_limited", [(b"retry-after", b"60")])
            if int(h.get(b"content-length") or 0) > MAX_BODY:
                self._note("body_too_large", ip, scope["path"])
                return await respond(413, "too_large")
            if method not in SAFE and (why := self._csrf(h)):
                self._note("csrf_blocked", ip, scope["path"], why=why)
                return await respond(403, "csrf")

        got = 0

        async def capped_receive():
            nonlocal got
            msg = await receive()
            if api and msg["type"] == "http.request":
                got += len(msg.get("body", b""))
                if got > MAX_BODY:  # chunked bodies have no Content-Length, so count what actually arrives
                    raise HTTPException(413, "too_large")
            return msg

        try:
            await self.app(scope, capped_receive, wrapped_send)
        finally:
            if api and scope["path"] != "/api/health":
                obs.event("request", method=scope["method"], path=scope["path"], status=status, ms=round((time.perf_counter() - t0) * 1000, 1), ip=ip)

    def _note(self, name: str, ip: str, path: str, **ctx):
        """Log a guard rejection at most 5 times per IP per minute and never more than 200 characters of path, so an attacker cannot
        use rejected requests to scroll the evidence of a real attack out of the (rotated, local) logs."""
        if self.limiter.hit(("log", name, ip), 5, 60):
            obs.event(name, 30, ip=ip, path=path[:200], **ctx)

    @staticmethod
    def _csrf(h: dict) -> str | None:
        """Cookies are SameSite=Strict already; this is the second layer for old browsers and odd clients."""
        site = h.get(b"sec-fetch-site")
        if site is not None:
            if site not in (b"same-origin", b"none"):
                return "fetch-site"
        elif (origin := h.get(b"origin")) is not None and origin.split(b"://", 1)[-1] != h.get(b"host", b""):
            return "origin"  # browsers without Fetch Metadata still send Origin on unsafe requests
        # A cross-site form can send a body-less/plain POST, but it cannot send JSON without a CORS preflight (which we never grant).
        if b"authorization" not in h and not h.get(b"content-type", b"").startswith(b"application/json"):
            return "content-type"
        return None


def client_ip(req: Request) -> str:
    return req.scope["state"]["ip"]
