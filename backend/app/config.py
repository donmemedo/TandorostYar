"""Environment-driven settings. Every security-relevant default is the safe one."""
from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


def _on(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0") == "1"


def _private_host(host: str) -> bool:
    """True for loopback, private ranges and single-label names such as a compose service (`sms-gw`)."""
    if host == "localhost" or "." not in host:
        return True
    try:
        a = ipaddress.ip_address(host)
        return a.is_private or a.is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class Settings:
    db_path: str = "pact.db"
    demo: bool = False  # seeds demo users, echoes OTP codes, enables fake top-up and manual week close. NEVER in production.
    admin_token: str | None = None  # Bearer token for POST /api/admin/settle; unset = endpoint answers 404
    sms_webhook_url: str | None = None  # POST {"phone","code","text"}; unset outside DEMO = login answers 503
    cookie_secure: bool = True
    proxy_hops: int = 0  # reverse proxies that append to X-Forwarded-For (0 = trust only the socket peer)
    tz: str = "Asia/Tehran"
    sms_hourly_budget: int = 300  # global cap on SMS sends per hour (SMS-pumping guard)
    rate_per_min: int = 300  # API requests per client IP per minute
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        demo = _on("DEMO")
        url = os.getenv("SMS_WEBHOOK_URL") or None
        if url and not url.startswith(("https://", "http://")):
            raise ValueError("SMS_WEBHOOK_URL must be an http(s) URL")
        if url and url.startswith("http://") and not demo and not _private_host(urlparse(url).hostname or ""):
            raise ValueError("SMS_WEBHOOK_URL over plain http is only allowed to a loopback/private/internal host: OTP codes would cross the internet in clear text")
        if (key := os.getenv("LOG_KEY")) and len(key) < 32:
            raise ValueError("LOG_KEY must be at least 32 characters")
        token = os.getenv("ADMIN_TOKEN") or None
        if token and len(token) < 32:
            raise ValueError("ADMIN_TOKEN must be at least 32 characters")
        return cls(
            db_path=os.getenv("DB_PATH", "pact.db"), demo=demo, admin_token=token, sms_webhook_url=url,
            cookie_secure=_on("COOKIE_SECURE", not demo), proxy_hops=max(0, int(os.getenv("TRUSTED_PROXY_HOPS", "0"))),
            tz=os.getenv("APP_TZ", "Asia/Tehran"), sms_hourly_budget=int(os.getenv("SMS_HOURLY_BUDGET", "300")), rate_per_min=int(os.getenv("RATE_LIMIT_PER_MIN", "300")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    @property
    def cookie_name(self) -> str:
        return "__Host-sid" if self.cookie_secure else "sid"  # __Host- blocks cookie tossing from sibling subdomains
