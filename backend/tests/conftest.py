import os
import tempfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import domain
from app.config import Settings
from app.main import create_app


@pytest.fixture
def tmp_path():  # RAM-backed when possible: SQLite fsyncs dominate test time on slow disks
    with tempfile.TemporaryDirectory(dir="/dev/shm" if os.path.isdir("/dev/shm") else None) as d:
        yield __import__("pathlib").Path(d)


def build(tmp_path, **kw):
    st = Settings(db_path=str(tmp_path / "t.db"), **{"demo": True, "cookie_secure": False, **kw})
    return st, TestClient(create_app(st), base_url="https://testserver" if st.cookie_secure else "http://testserver")


@pytest.fixture
def demo(tmp_path):
    st, c = build(tmp_path)
    with c:
        c.st = st
        yield c


@pytest.fixture
def prod(tmp_path):
    st, c = build(tmp_path, demo=False, cookie_secure=True, admin_token="a" * 40)
    with c:
        c.st = st
        yield c


def login(c, phone="09120000001"):
    code = c.post("/api/auth/otp", json={"phone": phone}).json()["code"]
    r = c.post("/api/auth/verify", json={"phone": phone, "code": code})
    assert r.status_code == 200, r.text
    return r


@pytest.fixture(autouse=True)
def fake_today(monkeypatch):
    """FAKE_TODAY=2026-10-17 pytest ... pins the clock to noon Tehran-time of that day, so the week-position logic
    (days left, early close, cancellation) can be exercised on every weekday."""
    if d := os.getenv("FAKE_TODAY"):
        y, m, day = map(int, d.split("-"))

        class Fake(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(y, m, day, 12, 0, tzinfo=tz or timezone.utc)

        monkeypatch.setattr(domain, "datetime", Fake)
