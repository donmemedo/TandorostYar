# فیت‌پیمان · FitPeyman

> Keep your word, get paid. Make a weekly health pact (gym ≥ 30 min, a daily step goal, or 3 logged meals), put money on each missed day, and split the pool with everyone who kept theirs.

Web app for Iran: **FastAPI** backend + **Next.js 16** frontend, Persian (RTL) and English (LTR), light and dark, responsive from phone to desktop.
PWA, Android and iOS builds come after the web app (see [docs/ROADMAP.md](docs/ROADMAP.md)).

| | |
|---|---|
| Money | Missed day = stake. Pool minus a 12 % fee is shared by winners by exposure (stake × days), each capped at 3× their own exposure; the rest goes to a health charity. Nobody ever pays more than their balance. No-money pacts work with an empty wallet. **`PAYOUT_CAP_X=0` makes it charity-only. Read the legal gate in [docs/ROADMAP.md](docs/ROADMAP.md) before any real money moves.** |
| Security | Phone + one-time-code login, hashed sessions, CSRF layers, streaming body cap, trusted-hop client IP, fail-closed rate limits, strict nonce CSP, hardened containers behind a single edge proxy. Details: [docs/SECURITY.md](docs/SECURITY.md). |
| Quality | 91 backend tests (the whole suite re-runs for every weekday in CI), unit tests for digit parsing, a 54-check black-box pen-test script against the live stack, headless-Chrome and axe accessibility scripts, CI with SAST, SCA, secret and image scanning and hardening assertions. |

## Run it (Docker)

```bash
DEMO=1 docker compose up -d --build      # first build takes a few minutes
open http://localhost:3330
```

`DEMO=1` seeds nine demo users, shows the one-time code on the sign-in screen, and enables fake top-ups and a manual "close the week" button.
Sign in with `09120000001` (the demo user with three pacts) and tap the demo-code chip. **Never run DEMO in production.**

Production: `cp .env.example .env`, leave `DEMO` unset, set `ADMIN_TOKEN` and `LOG_KEY` (`openssl rand -hex 32` each), `SMS_WEBHOOK_URL` and `SITE_ADDRESS=your.domain` (automatic HTTPS), publish 443 in `docker-compose.yml`. Without an SMS webhook login answers 503 by design.
If image builds cannot resolve DNS on your network: `docker compose -f docker-compose.yml -f docker-compose.hostnet.yml build`.

Only the **edge** (Caddy) publishes a port. It overwrites `X-Forwarded-For`, caps request bodies at 16 KB, hides `/api/admin/*` and the API docs, and is the one place the client IP is decided. The backend is reachable only from inside the compose network.

## Develop

```bash
# backend  (Python 3.12)
cd backend && python -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt && .venv/bin/pip install -r requirements-dev.txt
DEMO=1 DB_PATH=/tmp/dev.db .venv/bin/python -m app           # http://127.0.0.1:8330  (use `python -m app`, never bare uvicorn: see below)
.venv/bin/python -m pytest -q                                 # 91 tests
FAKE_TODAY=2026-10-22 .venv/bin/python -m pytest -q          # pin the clock to test any weekday

# frontend  (Node 24)
cd frontend && npm ci && npm run dev                          # http://localhost:3330, proxies /api to :8330
npx tsc --noEmit && npm test && npm run build
```

> **Run the API with `python -m app`.** It sets `proxy_headers=False`. With uvicorn's default, a client on the same host as a proxy can choose its own IP through `X-Forwarded-For` and walk around every rate limit (found by the live pen test, see [docs/PENTEST_REPORT.md](docs/PENTEST_REPORT.md)).

Attack your own running stack (DEMO only, creates throwaway users):

```bash
python3 scripts/pentest.py http://127.0.0.1:3330
```

## Layout

```
backend/app/        config · db (migrations, seed) · domain (settlement) · security (limiter, ASGI guard) · obs (JSON logs) · routes/
backend/tests/      pytest suite incl. one regression test per audit finding
frontend/app/       Next.js App Router pages: today, pacts, wallet, community, account, business
frontend/components Shell, Login, ui (spring sheet, hold-to-seal, rings), Toggles
frontend/lib        api (stale-while-revalidate cache), auth, i18n (fa/en, Persian UX vocabulary)
frontend/proxy.ts   per-request CSP nonce
edge/Caddyfile      the only public listener
scripts/            pentest.py (live black-box), backup.sh, e2e/ (headless Chrome + axe)
docs/               architecture, security, pen-test report, QA plan, operations, roadmap, audit register, screenshots
.github/workflows/  tests + SAST + SCA + secrets + image scans + live pen test
```

## Documentation

**Start with [LAST_Report.md](LAST_Report.md)** (everything that was done, what is left, what you must decide).

[Architecture](docs/ARCHITECTURE.md) · [Security & threat model](docs/SECURITY.md) · [Audit register (63 findings)](docs/AUDIT_FINDINGS.md) · [Pen-test report](docs/PENTEST_REPORT.md) · [QA plan](docs/QA.md) · [Operations runbook](docs/OPERATIONS.md) · [Threat-intel lifecycle](docs/THREAT_INTEL.md) · [Roadmap & role reviews](docs/ROADMAP.md) · [Original handoff](docs/HANDOFF.md)

## Known gaps (deliberate)

Check-ins are self-reported (GPS/QR/wearable verification is next). There is no payment gateway yet, so deposits and withdrawals do not exist outside DEMO. The in-memory limiter and SQLite assume **one** backend process. See [docs/ROADMAP.md](docs/ROADMAP.md) for owner decisions still open, including the legal review of a stake-and-pool model.

Licence: see [Licence](Licence).
