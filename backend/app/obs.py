"""Structured JSON logging with a per-request id. Security events never carry raw phone numbers or codes."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import sys
import time
from contextvars import ContextVar

rid_var: ContextVar[str] = ContextVar("rid", default="-")
log = logging.getLogger("fitpeyman")


class JsonFormatter(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        d = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(r.created)) + "Z", "lvl": r.levelname, "event": r.getMessage(),
             "rid": rid_var.get(), **getattr(r, "ctx", {})}
        if r.exc_info:
            d["exc"] = self.formatException(r.exc_info)
        return json.dumps(d, ensure_ascii=False, default=str)


def configure(level: str = "INFO"):
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    log.handlers[:] = [h]
    log.setLevel(level)
    log.propagate = False


def event(name: str, level: int = logging.INFO, **ctx):
    log.log(level, name, extra={"ctx": ctx})


# A plain hash of a phone number is reversible in minutes (about 1e9 candidates), so the reference is KEYED. Without LOG_KEY the key is
# random per process: references then correlate within one run only, which is why production should set LOG_KEY.
_KEY = (os.getenv("LOG_KEY") or "").encode() or secrets.token_bytes(32)


def ref(secret: str) -> str:
    """Stable reference for correlating events about one phone without writing it down. Not reversible without the key."""
    return hmac.new(_KEY, secret.encode(), hashlib.sha256).hexdigest()[:16]
