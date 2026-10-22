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
def assert_ledger(path):
    """The invariant the sweeper alarms on: every balance equals the sum of its ledger rows, and nothing is negative."""
    with sqlite3.connect(path) as con:
        bad = con.execute("SELECT u.id FROM users u WHERE u.balance != COALESCE((SELECT SUM(amount) FROM txns WHERE user_id=u.id),0) OR u.balance<0").fetchall()
    assert bad == [], f"ledger mismatch for users {bad}"


USER_ENDPOINTS = [("get", "/api/me"), ("get", "/api/dashboard"), ("get", "/api/wallet"), ("get", "/api/community"),
                  ("post", "/api/pacts"), ("post", "/api/pacts/1/checkin"), ("post", "/api/wallet/topup"),
                  ("post", "/api/settle"), ("delete", "/api/pacts/1"), ("patch", "/api/me"), ("delete", "/api/me")]


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
    jar = dict(demo.cookies)
    clients = [TestClient(demo.app, base_url="http://testserver", cookies=jar) for _ in range(3)]  # built BEFORE the threads, no lifespan each
    barrier, out = threading.Barrier(3), []

    def go(c, kind):
        barrier.wait()  # all three requests are released together, so they genuinely contend for the write lock
        out.append(c.post("/api/pacts", json={"type": kind, "target_days": 1, "stake": 250_000}).status_code)

    ts = [threading.Thread(target=go, args=(c, k)) for c, k in zip(clients, ("gym", "steps", "nutrition"))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(out) == [200, 200, 400]
    assert_ledger(demo.st.db_path)


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
    assert_ledger(demo.st.db_path)
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
    assert_ledger(demo.st.db_path)
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
        assert con.execute("PRAGMA user_version").fetchone()[0] == 4
        assert con.execute("SELECT daily_goal FROM pacts WHERE id=1").fetchone()[0] == 30  # the MVP pact got its goal copied on
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


def test_supported_entrypoint_never_lets_uvicorn_rewrite_the_client_ip():
    # Found live: with uvicorn's default proxy_headers a client beside a local proxy picked its own IP and defeated every limit.
    import pathlib
    src = (pathlib.Path(__file__).parent.parent / "app" / "__main__.py").read_text()
    assert "proxy_headers=False" in src
    assert "--no-proxy-headers" in (pathlib.Path(__file__).parent.parent / "README.md").read_text() if (pathlib.Path(__file__).parent.parent / "README.md").exists() else True


def test_a_user_who_cannot_cover_next_week_is_paused_and_told(demo):
    new_user(demo, "09129991111")  # a fresh user can only LOSE in the early close, so the outcome does not depend on the weekday
    assert demo.post("/api/pacts", json={"type": "gym", "target_days": 1, "stake": 10_000}).status_code == 200
    with sqlite3.connect(demo.st.db_path) as con:
        con.execute("UPDATE users SET balance=5000 WHERE phone='09129991111'")  # less than one week of exposure (10,000)
        con.execute("DELETE FROM txns WHERE user_id=(SELECT id FROM users WHERE phone='09129991111')")
        con.execute("INSERT INTO txns(user_id,amount,kind,day) SELECT id,5000,'topup','2026-01-01' FROM users WHERE phone='09129991111'")
    assert demo.post("/api/settle", json={}).status_code == 200
    d = demo.get("/api/dashboard").json()
    assert d["pacts"] == [] and d["paused"] is True
    assert demo.get("/api/wallet").json()["txns"][0]["kind"] == "paused"
    assert_ledger(demo.st.db_path)


def test_account_deletion_with_a_balance_is_refused_outside_demo(prod, monkeypatch):
    from app.routes import auth
    monkeypatch.setattr(auth, "send_sms", lambda st, phone, code: codes.append(code))
    codes: list = []
    prod.post("/api/auth/otp", json={"phone": "09125551234"})
    prod.post("/api/auth/verify", json={"phone": "09125551234", "code": codes[0]})
    with sqlite3.connect(prod.st.db_path) as con:
        con.execute("UPDATE users SET balance=1000 WHERE phone='09125551234'")
    assert prod.request("DELETE", "/api/me", json={}).json() == {"detail": "has_balance"}


# ---- production settlement path (the sweeper), exercised directly -------------------------------------------------------------
def _mk(path, tod):
    """A database at epoch = two weeks ago with: user 1 (complete pact in W-2), user 2 (pact created in W-1, misses), user 3 (cancelled)."""
    from datetime import timedelta

    from app.domain import week_start
    w0 = week_start(tod)
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        con.execute("UPDATE meta SET v=? WHERE k='epoch'", ((w0 - timedelta(14)).isoformat(),))
        for uid in (1, 2, 3):
            con.execute("INSERT INTO users(id,name,name_en,balance,phone) VALUES(?,?,?,?,?)", (uid, "u", "u", 1_000_000, f"0912888000{uid}"))
            con.execute("INSERT INTO txns(user_id,amount,kind,day) VALUES(?,?,?,?)", (uid, 1_000_000, "topup", (w0 - timedelta(30)).isoformat()))
        con.execute("INSERT INTO pacts(id,user_id,type,target_days,stake,daily_goal,created) VALUES(1,1,'gym',1,100000,30,?)", ((w0 - timedelta(14)).isoformat(),))
        con.execute("INSERT INTO checkins(pact_id,day,value) VALUES(1,?,45)", ((w0 - timedelta(13)).isoformat(),))  # W-2: done
        con.execute("INSERT INTO pacts(id,user_id,type,target_days,stake,daily_goal,created) VALUES(2,2,'gym',2,100000,30,?)", ((w0 - timedelta(7)).isoformat(),))  # created in W-1: no W-2 charge
        con.execute("INSERT INTO pacts(id,user_id,type,target_days,stake,created,ends) VALUES(3,3,'steps',1,50000,?,?)", ((w0 - timedelta(14)).isoformat(), (w0 - timedelta(8)).isoformat()))
    return w0


def test_the_sweeper_catches_up_several_weeks_idempotently_and_conserves_money(tmp_path):
    import time
    from datetime import timedelta

    from app.db import db, init
    from app.domain import settle_due, today
    st = Settings(db_path=str(tmp_path / "t.db"), cookie_secure=True)
    init(st)
    tod = today(st.zone)
    w0 = _mk(st.db_path, tod)
    with sqlite3.connect(st.db_path) as con:
        total0 = con.execute("SELECT SUM(balance) FROM users").fetchone()[0]
    with TestClient(create_app(st)):  # starting the app starts the real sweeper, which must settle both finished weeks
        for _ in range(100):
            with sqlite3.connect(st.db_path) as con:
                if con.execute("SELECT COUNT(*) FROM settlements").fetchone()[0] >= 2:
                    break
            time.sleep(0.05)
        else:
            pytest.fail("the sweeper did not settle the finished weeks")
    with db(st.db_path, write=True) as con:
        assert settle_due(con, tod) == []  # a rerun settles nothing: idempotent
    with sqlite3.connect(st.db_path) as con:
        rows = con.execute("SELECT week, pool, fee, charity FROM settlements WHERE week>=? ORDER BY week", ((w0 - timedelta(14)).isoformat(),)).fetchall()
        assert [r[0] for r in rows] == [(w0 - timedelta(14)).isoformat(), (w0 - timedelta(7)).isoformat()]
        bal = dict(con.execute("SELECT id, balance FROM users WHERE id IN (1,2,3)").fetchall())
        total1 = con.execute("SELECT SUM(balance) FROM users").fetchone()[0]
        ended = {r[0] for r in con.execute("SELECT id FROM pacts WHERE active=0")}
    assert bal[2] == 1_000_000 - 2 * 100_000  # missed both days of W-1 only; no charge for W-2, before the pact existed
    assert bal[3] == 1_000_000 - 50_000  # cancelled pact still paid its last week
    assert 3 in ended  # and ended with it
    assert bal[1] == 1_000_000 + 44_000 - 100_000  # W-2: won pool 50,000 - fee 6,000 (cap not reached); W-1: missed its one day
    assert total0 - total1 == sum(r[2] + r[3] for r in rows)  # money conserved: only fee + charity leave the system
    with sqlite3.connect(st.db_path) as con:
        assert con.execute("SELECT SUM(amount) FROM txns WHERE kind='reward'").fetchone()[0] == 44_000  # and the payout is in the ledger


def test_a_suspicious_clock_holds_settlement_until_an_operator_releases_it(tmp_path):
    import time

    from app.db import init
    from app.domain import today
    from app.main import sweep
    st = Settings(db_path=str(tmp_path / "t.db"), cookie_secure=True, admin_token="a" * 40)
    init(st)
    _mk(st.db_path, today(st.zone))

    def settlements():
        with sqlite3.connect(st.db_path) as con:
            return con.execute("SELECT COUNT(*) FROM settlements").fetchone()[0]

    sweep(st, jumped=True)  # the sweeper saw the wall clock and the monotonic clock disagree
    assert settlements() == 0
    with sqlite3.connect(st.db_path) as con:
        assert con.execute("SELECT v FROM meta WHERE k='held'").fetchone()[0].startswith("clock")
    sweep(st)  # still held on the next pass
    assert settlements() == 0
    with sqlite3.connect(st.db_path) as con:
        con.execute("DELETE FROM meta WHERE k='last_sweep'")
    with TestClient(create_app(st)) as c:  # booting the app starts another sweeper: it must respect the hold too
        for _ in range(200):  # every sweep writes last_sweep, so wait for the sweeper to have actually run
            with sqlite3.connect(st.db_path) as con:
                if con.execute("SELECT 1 FROM meta WHERE k='last_sweep'").fetchone():
                    break
            time.sleep(0.05)
        else:
            pytest.fail("the sweeper never ran")
        assert settlements() == 0
        assert c.post("/api/admin/settle", headers={"authorization": "Bearer " + "a" * 40}).status_code == 200  # the operator decides
    assert settlements() >= 2
    with sqlite3.connect(st.db_path) as con:
        assert con.execute("SELECT 1 FROM meta WHERE k='held'").fetchone() is None


def test_create_pact_never_settles_while_the_hold_is_on(tmp_path):
    from app.db import db, init
    from app.domain import settle_due, today
    st = Settings(db_path=str(tmp_path / "t.db"), cookie_secure=True)
    init(st)
    tod = today(st.zone)
    _mk(st.db_path, tod)
    with sqlite3.connect(st.db_path) as con:
        con.execute("INSERT INTO meta VALUES('held','test')")
    with db(st.db_path, write=True) as con:
        assert settle_due(con, tod) == []  # the guard lives in the shared function, so create_pact and every other caller obey it


def test_wall_clock_moving_backwards_also_holds(prod):
    import time

    from app.main import sweep
    with sqlite3.connect(prod.st.db_path) as con:
        con.execute("INSERT OR REPLACE INTO meta VALUES('last_sweep', ?)", (str(int(time.time()) + 7200),))
    sweep(prod.st)
    with sqlite3.connect(prod.st.db_path) as con:
        assert "back" in con.execute("SELECT v FROM meta WHERE k='held'").fetchone()[0]


def test_an_sms_outage_does_not_burn_the_login_budgets(tmp_path, monkeypatch):
    st, c = build(tmp_path, sms_hourly_budget=3)
    from app.routes import auth
    ok: list = []

    def flaky(st_, phone, code):
        if not ok:
            raise auth.HTTPException(503, "sms_unavailable")
        return None
    monkeypatch.setattr(auth, "send_sms", flaky)
    with c:
        for _ in range(8):  # eight failed sends from one phone: far past the 3-per-10-minutes and 3-per-hour budgets
            assert c.post("/api/auth/otp", json={"phone": "09121234321"}).status_code == 503
        ok.append(1)  # the provider recovers
        assert c.post("/api/auth/otp", json={"phone": "09121234321"}).status_code == 200  # nobody is locked out by the outage


def test_community_survives_a_settlement_that_pauses_users_inside_the_snapshot_window(demo):
    login(demo)
    assert demo.get("/api/community").status_code == 200  # snapshot cached with everyone's pacts
    with sqlite3.connect(demo.st.db_path) as con:
        con.execute("UPDATE pacts SET active=0")  # what a settlement does to users it pauses
    r = demo.get("/api/community")
    assert r.status_code == 200 and r.json()["leaderboard"]  # stale snapshot, but names come from the snapshot's own users


def test_database_refuses_negative_money_whatever_the_app_does(demo):
    with sqlite3.connect(demo.st.db_path) as con:
        with pytest.raises(sqlite3.DatabaseError, match="negative"):
            con.execute("UPDATE users SET balance=-1 WHERE id=1")
        with pytest.raises(sqlite3.DatabaseError, match="negative"):
            con.execute("UPDATE users SET points=-1 WHERE id=1")


def test_the_demo_ledger_explains_every_balance(demo):
    with sqlite3.connect(demo.st.db_path) as con:
        bad = con.execute("SELECT COUNT(*) FROM users u WHERE u.balance != COALESCE((SELECT SUM(amount) FROM txns WHERE user_id=u.id),0)").fetchone()[0]
    assert bad == 0


def test_health_reports_how_far_settlement_has_got(demo):
    assert "settled_through" in demo.get("/api/health").json()


# ---- red/blue panel findings ----------------------------------------------------------------------------------------------
def test_the_daily_otp_send_cap_survives_logins_and_the_sweeper(demo):
    from app.main import sweep
    p = "09127654321"
    login(demo, p)  # a successful login used to delete the row that holds the daily counter
    sweep(demo.st)  # so did the sweeper
    with sqlite3.connect(demo.st.db_path) as con:
        assert con.execute("SELECT sent FROM otps WHERE phone=?", (p,)).fetchone()[0] >= 1
        con.execute("UPDATE otps SET sent=10 WHERE phone=?", (p,))
    assert demo.post("/api/auth/otp", json={"phone": p}).status_code == 429  # 11th send in 24 h: refused


def test_only_a_finished_daily_window_is_purged(demo):
    import time

    from app.main import sweep
    with sqlite3.connect(demo.st.db_path) as con:
        con.execute("INSERT INTO otps(phone,code_hash,expires,win_start,sent) VALUES('09120001111','x',1,?,5)", (int(time.time()) - 100,))
        con.execute("INSERT INTO otps(phone,code_hash,expires,win_start,sent) VALUES('09120002222','x',1,?,5)", (int(time.time()) - 90_000,))
    sweep(demo.st)
    with sqlite3.connect(demo.st.db_path) as con:
        left = {r[0] for r in con.execute("SELECT phone FROM otps")}
    assert "09120001111" in left and "09120002222" not in left


def test_ipv6_clients_are_keyed_by_subscriber_not_by_address():
    from app.security import peer_ip
    sc = lambda ip, xff=None: {"client": (ip, 1), "headers": [(b"x-forwarded-for", xff.encode())] if xff else []}  # noqa: E731
    assert peer_ip(sc("2001:db8:1:2:aaaa::1"), 0) == peer_ip(sc("2001:db8:1:2:bbbb::9"), 0)  # same /64: one client
    assert peer_ip(sc("2001:db8:1:3::1"), 0) != peer_ip(sc("2001:db8:1:2::1"), 0)
    assert peer_ip(sc("::ffff:203.0.113.7"), 0) == "203.0.113.7"
    assert peer_ip(sc("172.18.0.2", "9.9.9.9, 2001:db8:5:5:1::2"), 1) == peer_ip(sc("2001:db8:5:5:ffff::3"), 0)
    assert peer_ip(sc("172.18.0.2", "not-an-ip"), 1) == "172.18.0.2"  # garbage never becomes a key


def test_provider_rejections_still_cost_the_caller_but_outages_do_not(tmp_path, monkeypatch):
    import urllib.error

    from app.routes import auth
    st, c = build(tmp_path, demo=False, cookie_secure=True, sms_webhook_url="https://sms.example/hook")
    mode = {"v": "reject"}

    def fake_open(req, timeout):
        if mode["v"] == "reject":
            raise urllib.error.HTTPError(req.full_url, 400, "bad number", {}, None)
        raise TimeoutError("provider down")
    monkeypatch.setattr(auth.urllib.request, "urlopen", fake_open)
    monkeypatch.setitem(auth._sms, "fails", 0)
    monkeypatch.setitem(auth._sms, "until", 0.0)
    with c:
        codes = [c.post("/api/auth/otp", json={"phone": f"0912555{i:04d}"}).status_code for i in range(12)]
        assert codes[:10] == [400] * 10 and codes[10] == 429  # numbers the provider refuses burn the per-IP budget (10 per 10 min)
        mode["v"] = "down"
        assert c.post("/api/auth/otp", json={"phone": "09125559999"}).status_code == 429  # same IP is still capped even during an outage


def test_sms_circuit_breaker_stops_hammering_a_dead_provider(tmp_path, monkeypatch):
    from app.routes import auth
    st, c = build(tmp_path, demo=False, cookie_secure=True, sms_webhook_url="https://sms.example/hook")
    calls = []
    monkeypatch.setattr(auth.urllib.request, "urlopen", lambda req, timeout: calls.append(1) or (_ for _ in ()).throw(TimeoutError()))
    monkeypatch.setitem(auth._sms, "fails", 0)
    monkeypatch.setitem(auth._sms, "until", 0.0)
    with c:
        for i in range(6):
            assert c.post("/api/auth/otp", json={"phone": f"0912777{i:04d}"}).status_code == 503
    assert len(calls) == 3  # after three straight failures the app stops calling the provider for a minute


def test_rejected_requests_spend_the_rate_limit_budget_too(tmp_path):
    st, c = build(tmp_path, rate_per_min=5)
    with c:
        c.app.state.limiter._clock = lambda: 1000.0
        codes = [c.post("/api/wallet/topup", headers={"sec-fetch-site": "cross-site", "content-type": "application/json"}, json={}).status_code for _ in range(8)]
    assert codes[:5] == [403] * 5 and codes[5:] == [429] * 3  # a stream of cheap 403s cannot be free


def test_guard_rejections_are_logged_a_bounded_number_of_times(tmp_path, caplog, monkeypatch):
    import logging

    from app import obs
    st, c = build(tmp_path)  # create_app() configures the logger, so adjust it afterwards
    monkeypatch.setattr(obs.log, "propagate", True)  # our logger is isolated from the root handler; let pytest see it
    with c, caplog.at_level(logging.WARNING, logger="fitpeyman"):
        c.app.state.limiter._clock = lambda: 1000.0
        for _ in range(50):
            c.post("/api/wallet/topup" + "x" * 500, headers={"sec-fetch-site": "cross-site", "content-type": "application/json"}, json={})
    logged = [r for r in caplog.records if r.getMessage() == "csrf_blocked"]
    assert 1 <= len(logged) <= 5 and all(len(r.ctx["path"]) <= 200 for r in logged)


def test_log_phone_references_are_keyed_not_a_bare_hash():
    import hashlib

    from app import obs
    assert obs.ref("09120000001") == obs.ref("09120000001") != obs.ref("09120000002")
    assert obs.ref("09120000001") != hashlib.sha256(b"09120000001").hexdigest()[:16]  # an unkeyed hash is reversible in minutes
    assert len(obs.ref("x")) == 16


def test_an_easy_step_goal_cannot_be_bought_through_the_api(demo):
    new_user(demo)
    assert demo.post("/api/pacts", json={"type": "steps", "target_days": 1, "stake": 20_000, "daily_goal": 1000}).status_code == 422
    assert demo.post("/api/pacts", json={"type": "steps", "target_days": 1, "stake": 20_000, "daily_goal": 6000}).status_code == 200


def test_sign_out_everywhere_revokes_every_device(tmp_path):
    st, c1 = build(tmp_path)
    with c1:
        login(c1, "09126660001")
        c2 = TestClient(c1.app, base_url="http://testserver")
        login(c2, "09126660001")  # a second device
        assert c1.get("/api/me").status_code == 200 and c2.get("/api/me").status_code == 200
        assert c1.post("/api/auth/logout-all", json={}).status_code == 200
        assert c2.get("/api/me").status_code == 401  # the stolen/lost phone is cut off too


def test_account_deletion_erases_activity_pacts_and_otp_row(demo):
    login(demo, "09125550007")
    uid = demo.get("/api/me").json()["id"]
    with sqlite3.connect(demo.st.db_path) as con:
        con.execute("INSERT INTO pacts(id,user_id,type,target_days,stake,daily_goal,created,active,ends) VALUES(9001,?,'gym',1,10000,30,'2026-01-01',0,'2026-01-02')", (uid,))
        con.execute("INSERT INTO checkins(pact_id,day,value) VALUES(9001,'2026-01-01',45)")
    assert demo.request("DELETE", "/api/me", json={}).status_code == 200  # demo: a balance does not block deletion
    with sqlite3.connect(demo.st.db_path) as con:
        assert con.execute("SELECT COUNT(*) FROM checkins WHERE pact_id=9001").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM pacts WHERE user_id=?", (uid,)).fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM otps WHERE phone='09125550007'").fetchone()[0] == 0
        assert con.execute("SELECT phone FROM users WHERE id=?", (uid,)).fetchone()[0] is None


@pytest.mark.parametrize("url,ok", [("https://sms.example/h", True), ("http://sms-gateway/h", True), ("http://10.0.0.5/h", True), ("http://127.0.0.1:9/h", True),
                                    ("http://sms.example.com/h", False), ("http://8.8.8.8/h", False)])
def test_plain_http_sms_webhooks_are_refused_unless_internal(monkeypatch, url, ok):
    monkeypatch.setenv("SMS_WEBHOOK_URL", url)
    if ok:
        assert Settings.from_env().sms_webhook_url == url
    else:
        with pytest.raises(ValueError):
            Settings.from_env()


def test_log_key_must_be_long_enough(monkeypatch):
    monkeypatch.setenv("LOG_KEY", "short")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_the_public_business_chart_is_served_from_the_shared_cache(demo):
    a = demo.get("/api/business").json()
    with sqlite3.connect(demo.st.db_path) as con:
        con.execute("DELETE FROM checkins")  # a fresh query would now return zeros
    assert demo.get("/api/business").json()["daily"] == a["daily"]


def test_a_huge_pact_id_is_a_validation_error_not_a_500(demo):
    new_user(demo)
    for pid in (10**23, -1, 0):
        assert demo.post(f"/api/pacts/{pid}/checkin", json={"value": 40}).status_code in (404, 422)
        assert demo.request("DELETE", f"/api/pacts/{pid}", json={}).status_code in (404, 422)


def test_a_no_money_pact_is_possible_with_an_empty_wallet_and_settles_without_dividing_by_zero(demo):
    login(demo, "09125550123")  # brand-new user: balance 0, the only kind of user a production signup is before payments exist
    r = demo.post("/api/pacts", json={"type": "gym", "target_days": 1, "stake": 0})
    assert r.status_code == 200 and r.json()["goal"] == 30
    assert demo.post("/api/pacts", json={"type": "steps", "target_days": 1, "stake": 5000}).status_code == 422  # real money: 10,000 minimum
    pid = r.json()["id"]
    assert demo.post(f"/api/pacts/{pid}/checkin", json={"value": 45}).json()["done_days"] == 1  # a winner whose weight is 0
    assert demo.post("/api/settle", json={}).status_code == 200  # total_w == 0 must not raise ZeroDivisionError
    assert_ledger(demo.st.db_path)


def test_money_writes_fail_closed_while_the_settlement_hold_is_on(demo):
    new_user(demo, "09129992222")
    pid = demo.post("/api/pacts", json={"type": "gym", "target_days": 1, "stake": 10_000}).json()["id"]
    with sqlite3.connect(demo.st.db_path) as con:
        con.execute("INSERT INTO meta VALUES('held','clock moved back')")
    assert demo.post("/api/pacts", json={"type": "steps", "target_days": 1, "stake": 10_000}).json() == {"detail": "held"}
    assert demo.post(f"/api/pacts/{pid}/checkin", json={"value": 45}).status_code == 503
    assert demo.get("/api/dashboard").status_code == 200  # reading stays available
    with sqlite3.connect(demo.st.db_path) as con:
        con.execute("DELETE FROM meta WHERE k='held'")
    assert demo.post(f"/api/pacts/{pid}/checkin", json={"value": 45}).status_code == 200  # released: normal again
