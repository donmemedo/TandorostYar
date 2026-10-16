import sqlite3
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security import Limiter

from .conftest import build, login

JSON = {"content-type": "application/json"}
USER_ENDPOINTS = [("get", "/api/me"), ("get", "/api/dashboard"), ("get", "/api/wallet"), ("get", "/api/community"),
                  ("post", "/api/pacts"), ("post", "/api/pacts/1/checkin"), ("post", "/api/wallet/topup"),
                  ("post", "/api/rewards/gym20/redeem"), ("post", "/api/settle"), ("delete", "/api/pacts/1"), ("patch", "/api/me"), ("delete", "/api/me")]


@pytest.mark.parametrize("method,path", USER_ENDPOINTS)
def test_every_user_endpoint_requires_login(demo, method, path):
    assert demo.request(method.upper(), path, json={} if method != "get" else None).status_code == 401


def test_login_cookie_flags_in_production(prod, monkeypatch):
    from app.routes import auth
    monkeypatch.setattr(auth, "send_sms", lambda st, phone, code: sent.append(code))
    sent: list = []
    r = prod.post("/api/auth/otp", json={"phone": "09123334444"})
    assert r.status_code == 200 and "code" not in r.json()  # production never echoes the code
    r = prod.post("/api/auth/verify", json={"phone": "09123334444", "code": sent[0]})
    c = r.headers["set-cookie"]
    assert c.startswith("__Host-sid=") and "HttpOnly" in c and "Secure" in c and "SameSite=strict" in c and "Path=/" in c and "Domain" not in c
    assert prod.get("/api/me").status_code == 200


def test_production_without_sms_provider_refuses_login(prod):
    assert prod.post("/api/auth/otp", json={"phone": "09123334444"}).json() == {"detail": "sms_unavailable"}


def test_demo_only_features_are_dark_in_production(prod, monkeypatch):
    for path in ("/api/docs", "/api/openapi.json", "/docs", "/openapi.json"):
        assert prod.get(path).status_code == 404
    from app.routes import auth
    monkeypatch.setattr(auth, "send_sms", lambda st, phone, code: codes.append(code))
    codes: list = []
    prod.post("/api/auth/otp", json={"phone": "09125550000"})
    prod.post("/api/auth/verify", json={"phone": "09125550000", "code": codes[0]})
    assert prod.post("/api/wallet/topup", json={}).status_code == 503
    assert prod.post("/api/settle", json={}).status_code == 404


def test_otp_locks_after_five_wrong_guesses_and_resend_does_not_help(demo):
    p = "09127770000"
    code = demo.post("/api/auth/otp", json={"phone": p}).json()["code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert demo.post("/api/auth/verify", json={"phone": p, "code": wrong}).json() == {"detail": "code"}
    assert demo.post("/api/auth/verify", json={"phone": p, "code": code}).status_code == 429  # even the right code is refused
    assert demo.post("/api/auth/otp", json={"phone": p}).status_code == 429  # a resend cannot refill the guesses


def test_otp_is_single_use_and_expires(demo):
    p = "09127771111"
    code = demo.post("/api/auth/otp", json={"phone": p}).json()["code"]
    assert demo.post("/api/auth/verify", json={"phone": p, "code": code}).status_code == 200
    assert demo.post("/api/auth/verify", json={"phone": p, "code": code}).status_code == 400
    code = demo.post("/api/auth/otp", json={"phone": p}).json()["code"]
    with sqlite3.connect(demo.st.db_path) as con:
        con.execute("UPDATE otps SET expires=1")
    assert demo.post("/api/auth/verify", json={"phone": p, "code": code}).status_code == 400


def test_otp_per_phone_limit_and_global_sms_budget(tmp_path):
    st, c = build(tmp_path, sms_hourly_budget=4)
    with c:
        assert [c.post("/api/auth/otp", json={"phone": "09121110000"}).status_code for _ in range(4)] == [200, 200, 200, 429]
        assert c.post("/api/auth/otp", json={"phone": "09121110001"}).status_code == 200  # 4th global send
        assert c.post("/api/auth/otp", json={"phone": "09121110002"}).status_code == 429  # budget spent


@pytest.mark.parametrize("raw,ok", [("۰۹۱۲۱۱۱۲۲۲۲", True), ("+98 912 111 2222", True), ("00989121112222", True), ("9121112222", True),
                                    ("０９１２１１１２２２２", False), ("0912111222", False), ("08121112222", False), ("0912111222a2x", False), ("09121112222;", False)])
def test_phone_normalisation(demo, raw, ok):
    assert (demo.post("/api/auth/otp", json={"phone": raw}).status_code == 200) is ok


def test_logout_kills_the_session(demo):
    login(demo)
    assert demo.get("/api/me").status_code == 200
    old = demo.cookies.get("sid")
    demo.post("/api/auth/logout", json={})
    demo.cookies.set("sid", old)  # replay the stolen cookie
    assert demo.get("/api/me").status_code == 401


def test_idor_other_users_pacts_are_invisible(demo):
    login(demo, "09120000001")
    mine = demo.get("/api/dashboard").json()["pacts"][0]["id"]
    demo.post("/api/auth/logout", json={})
    login(demo, "09120000002")
    assert demo.post(f"/api/pacts/{mine}/checkin", json={"value": 40}).json() == {"detail": "not_found"}
    assert demo.delete(f"/api/pacts/{mine}", headers=JSON).status_code == 404


def test_csrf_layers(demo):
    login(demo)
    assert demo.post("/api/wallet/topup", json={}, headers={"sec-fetch-site": "cross-site"}).status_code == 403
    assert demo.post("/api/wallet/topup", json={}, headers={"sec-fetch-site": "same-site"}).status_code == 403
    assert demo.post("/api/wallet/topup", headers={"content-type": "text/plain"}, content="x").status_code == 403  # form-style post
    assert demo.post("/api/wallet/topup").status_code == 403  # body-less simple request
    assert demo.post("/api/wallet/topup", json={}, headers={"origin": "https://evil.example"}).status_code == 403  # old browser
    assert demo.post("/api/wallet/topup", json={}, headers={"origin": "http://testserver"}).status_code == 200
    assert demo.post("/api/wallet/topup", json={}, headers={"sec-fetch-site": "same-origin"}).status_code == 200


def test_body_cap_applies_to_content_length_and_chunked_bodies(demo):
    big = b'{"phone":"' + b"1" * 20_000 + b'"}'
    assert demo.post("/api/auth/otp", content=big, headers=JSON).status_code == 413
    chunks = (big[i:i + 4096] for i in range(0, len(big), 4096))  # no Content-Length: Transfer-Encoding chunked
    r = demo.post("/api/auth/otp", content=chunks, headers=JSON)
    assert r.status_code == 413 and r.json() == {"detail": "too_large"}


def test_x_forwarded_for_is_ignored_without_a_trusted_proxy(tmp_path):
    st, c = build(tmp_path)
    with c:
        c.app.state.limiter._clock = lambda: 1000.0  # freeze the window so the count cannot straddle a minute boundary
        codes = {c.get("/api/health", headers={"x-forwarded-for": f"10.0.{i // 250}.{i % 250}"}).status_code for i in range(320)}
        assert 429 in codes  # rotating the header did not reset the per-IP window


def test_only_the_trusted_proxy_hop_decides_the_client_ip(tmp_path):
    st, c = build(tmp_path, proxy_hops=1)
    with c:
        c.app.state.limiter._clock = lambda: 1000.0
        spoof = [c.get("/api/health", headers={"x-forwarded-for": f"6.6.{i // 250}.{i % 250}, 203.0.113.9"}).status_code for i in range(320)]
        assert 429 in spoof  # leftmost entries are attacker-chosen; the proxy-appended one is what counts
        assert c.get("/api/health", headers={"x-forwarded-for": "198.51.100.7"}).status_code == 200  # a different real client is unaffected


def test_limiter_fails_closed_instead_of_forgetting_counters():
    lim = Limiter(cap=3)
    assert lim.hit("victim", 1, 600) and not lim.hit("victim", 1, 600)
    lim.hit("a", 5, 600), lim.hit("b", 5, 600)
    assert not lim.hit("flood", 5, 600)  # table full of live keys: new key refused
    assert not lim.hit("victim", 1, 600)  # the important counter survived the flood


def test_admin_endpoint_hides_and_resists(prod):
    ok = {"authorization": "Bearer " + "a" * 40}
    assert prod.post("/api/admin/settle", headers=ok).status_code == 200
    for bad in (JSON, {"authorization": "Bearer nope"}, {"authorization": "Bearer " + "a" * 39}, {"authorization": ("Bearer ünï" + "a" * 40).encode("utf-8")}):
        assert prod.post("/api/admin/settle", headers=bad).status_code == 404
    st = Settings(db_path=prod.st.db_path, admin_token=None)
    with TestClient(create_app(st)) as c:
        assert c.post("/api/admin/settle", headers=ok).status_code == 404  # unset token disables the endpoint


def test_admin_token_must_be_long_enough(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "short")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_sms_webhook_must_be_http(monkeypatch):
    monkeypatch.setenv("SMS_WEBHOOK_URL", "file:///etc/passwd")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_headers_and_request_id(demo):
    r = demo.get("/api/health", headers={"x-request-id": "abc-12345678"})
    h = r.headers
    assert h["x-request-id"] == "abc-12345678" and h["cache-control"] == "no-store" and h["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in h["content-security-policy"] and "server-timing" in h
    assert demo.get("/api/health", headers={"x-request-id": "bad id\t"}).headers["x-request-id"] != "bad id\t"


def test_validation_errors_do_not_echo_input(demo):
    r = demo.post("/api/auth/otp", json={"phone": 5})
    assert r.status_code == 422 and r.json() == {"detail": "invalid"}


def test_display_names_reject_bidi_tricks_but_keep_zwnj(demo):
    login(demo)
    assert demo.patch("/api/me", json={"name": "ali‮gpj"}).json() == {"detail": "name"}
    assert demo.patch("/api/me", json={"name": "ali​x"}).status_code == 400
    assert demo.patch("/api/me", json={"name": "می‌خواهم"}).status_code == 200


def test_new_users_get_a_random_public_handle_not_their_phone(demo, monkeypatch):
    from app.routes import auth
    monkeypatch.setattr(auth.secrets, "randbelow", lambda n: 4321 % n)
    login(demo, "09127777777")
    assert demo.get("/api/me").json()["name_en"] == "User 5321"  # 1000 + 4321, nothing taken from 7777


def new_user(c, phone="09129990000"):
    login(c, phone)
    c.post("/api/wallet/topup", json={})  # 500k
    return c


def test_create_pact_rules(demo):
    new_user(demo)
    ok = {"type": "gym", "target_days": 1, "stake": 100_000}
    assert demo.post("/api/pacts", json=ok).status_code == 200
    assert demo.post("/api/pacts", json=ok).json() == {"detail": "exists"}
    assert demo.post("/api/pacts", json={**ok, "type": "steps", "stake": 450_000}).json() == {"detail": "balance"}  # 100k already held
    assert demo.post("/api/pacts", json={**ok, "type": "steps", "target_days": 8}).status_code == 422
    assert demo.post("/api/pacts", json={**ok, "type": "steps", "stake": 5}).status_code == 422


def test_concurrent_creates_cannot_spend_the_same_money_twice(demo):
    new_user(demo)  # balance 500k, three pacts of 250k each cannot all fit
    out, jar = [], dict(demo.cookies)

    def go(kind):
        with TestClient(demo.app, base_url="http://testserver", cookies=jar) as c:
            out.append(c.post("/api/pacts", json={"type": kind, "target_days": 1, "stake": 250_000}).status_code)

    ts = [threading.Thread(target=go, args=(k,)) for k in ("gym", "steps", "nutrition")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(out) == [200, 200, 400]


def test_checkin_caps_and_goal_points(demo):
    new_user(demo)
    pid = demo.post("/api/pacts", json={"type": "gym", "target_days": 1, "stake": 20_000}).json()["id"]
    assert demo.post(f"/api/pacts/{pid}/checkin", json={"value": 301}).json() == {"detail": "value"}
    assert demo.post(f"/api/pacts/{pid}/checkin", json={"value": 45}).json()["done_days"] == 1
    assert demo.get("/api/me").json()["points"] == 10
    for _ in range(2):
        demo.post(f"/api/pacts/{pid}/checkin", json={"value": 20})
    assert demo.post(f"/api/pacts/{pid}/checkin", json={"value": 20}).json() == {"detail": "limit"}  # 3 rows a day


def test_demo_settlement_is_idempotent_conserves_money_and_freezes_the_week(demo):
    login(demo)
    with sqlite3.connect(demo.st.db_path) as con:
        before = con.execute("SELECT SUM(balance) FROM users").fetchone()[0]
    r = demo.post("/api/settle", json={})
    assert r.status_code == 200
    s = r.json()
    with sqlite3.connect(demo.st.db_path) as con:
        after = con.execute("SELECT SUM(balance) FROM users").fetchone()[0]
        assert con.execute("SELECT MIN(balance) FROM users").fetchone()[0] >= 0
    assert before - after == s["fee"] + s["charity"]
    assert demo.post("/api/settle", json={}).json() == {"detail": "settled"}
    pid = demo.get("/api/dashboard").json()["pacts"]
    if pid:
        assert demo.post(f"/api/pacts/{pid[0]['id']}/checkin", json={"value": 40}).json() == {"detail": "settled"}


def test_cancelled_pact_still_pays_this_weeks_penalty_and_blocks_deletion(demo):
    new_user(demo)
    pid = demo.post("/api/pacts", json={"type": "gym", "target_days": 1, "stake": 100_000}).json()["id"]
    assert demo.delete(f"/api/pacts/{pid}", headers=JSON).status_code == 200
    assert demo.delete("/api/me", headers=JSON).json() == {"detail": "active_pacts"}
    demo.post("/api/settle", json={})
    me = demo.get("/api/me").json()
    assert me["balance"] == 400_000  # 500k - the missed day
    assert demo.get("/api/dashboard").json()["pacts"] == []  # ended with the week


def test_mvp_database_migrates_without_crashing_or_back_charging(tmp_path):
    path = tmp_path / "mvp.db"
    with sqlite3.connect(path) as con:  # the exact MVP schema, no phone/created columns
        con.executescript("""
        CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT, name_en TEXT, balance INTEGER, points INTEGER);
        CREATE TABLE pacts(id INTEGER PRIMARY KEY, user_id INTEGER, type TEXT, target_days INTEGER, stake INTEGER, daily_goal INTEGER, active INTEGER DEFAULT 1);
        CREATE TABLE checkins(id INTEGER PRIMARY KEY, pact_id INTEGER, day TEXT, value INTEGER, note TEXT);
        CREATE TABLE txns(id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER, kind TEXT, day TEXT);
        CREATE TABLE settlements(week TEXT PRIMARY KEY, pool INTEGER, fee INTEGER, charity INTEGER, winners INTEGER);
        INSERT INTO users VALUES(1,'a','a',1000000,0); INSERT INTO pacts VALUES(1,1,'gym',4,50000,NULL,1);""")
    with TestClient(create_app(Settings(db_path=str(path)))):
        pass
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT balance FROM users").fetchone()[0] == 1_000_000  # no retroactive penalty
        assert con.execute("SELECT COUNT(*) FROM settlements").fetchone()[0] == 0
        assert con.execute("PRAGMA user_version").fetchone()[0] == 2
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO users(name,name_en,phone) VALUES('x','x','0912')")
            con.execute("INSERT INTO users(name,name_en,phone) VALUES('y','y','0912')")


def test_leaderboard_never_exposes_phone_numbers(demo):
    login(demo)
    body = demo.get("/api/community").text
    assert "0912" not in body and "phone" not in body


def test_business_page_is_public_and_aggregate_only(demo):
    r = demo.get("/api/business")
    assert r.status_code == 200 and set(r.json()) == {"members", "pacts", "completion", "daily"}
