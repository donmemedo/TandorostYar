> **Historical document (2026-10-02).** Its to-do list has been worked through on branch `feat/security-hardening-redesign`. Current state and what remains: [../LAST_Report.md](../LAST_Report.md), [ROADMAP.md](ROADMAP.md), [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md). Note that its advice to set `TRUST_PROXY=1` behind the Next proxy was **wrong** (the proxy forwards a client-chosen `X-Forwarded-For`); the Caddy edge and `python -m app` replace it.

# FitPeyman security/perf/UX hardening: session handoff

Status as of 2026-10-02. Written so another model or engineer can continue without the original chat.

## 1. The task

The owner's request, verbatim:

> use red team agents and blue team agents and security skills to audit and solve all problems and of course do pen test for this project, also add performance to all security things. and for ui/ux use /apple-design you can use how much tokens you want just try to finish all works under 5 hours

In practice, that means:

- Audit the whole app for security, attacking it (red team) and hardening it (blue team).
- Fix every finding, including the "demo shortcuts" listed in the README. The owner wants real money to move later.
- Pen-test the running stack after the fixes.
- Every security fix should also be fast. Performance is part of the scope.
- Redo the UI/UX following Apple's design principles. The rules are in `~/.claude/skills/apple-design/SKILL.md`.

Rules that apply to anyone working in this repo:

- **Persian UX copy** must follow `~/references/persian-ux-vocab/README.md`. For example, a wrong password or code is «نادرست», never «اشتباه». The plural of سفارش is «سفارش‌ها», not «سفارشات».
- **Minimal code (the "ponytail" style).** Reuse what exists, use the stdlib and native platform features first, keep diffs small, and add no new abstractions or dependencies unless needed. Security, validation and accessibility are never cut.
- **Commits.** Only commit when the owner asks. Nothing from this session has been committed.

## 2. The project in one paragraph

FitPeyman (فیت‌پیمان) is a health "pact" app for Iran. A user makes a weekly pact: gym ≥30 min, a daily step goal, or 3 logged meals. They stake Toman on each missed day. Missed-day money forms a pool. Winners split the pool by stake after a 12% fee, and any leftover goes to a health charity. The backend is FastAPI with stdlib `sqlite3` in one file, `backend/main.py`. The frontend is Next.js 16 App Router with Tailwind 4 and lucide icons. Every page is a client component, and Next rewrites `/api/*` to the backend. `docker-compose.yml` runs the frontend on :3330 and the backend on :8330, which maps to container port 8000.

## 3. What was done

### 3.1 Baseline checks, before any change

| Check | Result |
|---|---|
| `npx tsc --noEmit` in frontend | pass |
| `npm run build` in frontend | pass, 6 dynamic routes |
| `python test_settle.py` | pass |
| `pip-audit -r backend/requirements.txt` | no known vulnerabilities |
| `npm audit` | 0 vulnerabilities across 103 dependencies |
| bandit on backend | 3 × B608 "SQL string building". These are false positives: only constant fragments are interpolated and all values are bound. |
| semgrep | 1st run timed out downloading rule packs. 2nd run printed nothing. Treat semgrep as **not run**. |

### 3.2 Multi-agent audit workflow: stopped, produced nothing

A 12-lens audit workflow was launched: find, then dedup, then 3-lens adversarial verify, then synthesis. Usage limits (HTTP 429) killed it during the Find phase, so it returned **no findings**. The script is saved and can be re-run in Claude Code:

`~/.claude/projects/-home-makhataei-Projects-Mine-TandorostYar/feb9ac2b-9615-41cb-8ceb-a8e6c96706aa/workflows/scripts/fitpeyman-audit-wf_13dbc4e4-9b3.js`

The findings in sections 3.3 and 4 come from a manual line-by-line read of every source file instead.

### 3.3 Backend rewrite: `backend/main.py`, uncommitted, smoke-tested

The file grew from 253 to 559 lines. Endpoint paths and response shapes are unchanged, except that every user endpoint now requires login.

| Problem in the MVP | Fix now in `main.py` |
|---|---|
| No auth. Every request acted as hardcoded user `ME=1`. | Phone + OTP login: `/api/auth/otp`, `/api/auth/verify`, `/api/auth/logout`, `GET`/`PATCH /api/me`. Session tokens are random 32-byte values stored as SHA-256 hashes. The cookie is `sid`, HttpOnly, SameSite=Strict, Path=/api, lasts 30 days, and is Secure unless DEMO. The `current_user` dependency is on every user endpoint. |
| `POST /api/wallet/topup` gave free money to anyone. | Works only when `DEMO=1`, otherwise returns 503. Real deposits need a payment-gateway callback, which is not built yet. |
| `POST /api/settle` let anyone close the week. | Works only when `DEMO=1`. Real settlement is automatic: `settle_due()` runs at startup and every 10 minutes on a thread. It settles each finished, unsettled week of the last 4 and is idempotent because `week` is the primary key. An operator can also trigger it with `POST /api/admin/settle` and `Authorization: Bearer $ADMIN_TOKEN`. The token is compared in constant time, and the endpoint returns 404 when the token is unset. |
| DB connections were never closed. | The `db()` context manager always closes the connection. |
| Check-then-act races in create pact, settle, and check-in points. | `db(write=True)` opens `BEGIN IMMEDIATE`, commits on success, and rolls back on any error. |
| No constraints and no indexes. | Partial unique index: one active pact per user and type. Indexes on `checkins(pact_id, day)`, `pacts(user_id, active)`, `txns(user_id, id)` and `sessions(expires)`. WAL mode, `busy_timeout` of 5s, and `foreign_keys=ON`. |
| N+1 queries: 2 per pact, for all users, on every page. | `pacts_view()` now runs 3 queries in total for any number of pacts. `done_days()` and `streak()` each run one grouped query. |
| `date.today()` used the server's UTC clock, so Iranian evenings landed on the wrong day. | `today()` uses `Asia/Tehran`, configurable with `APP_TZ`. |
| Unlimited check-in rows, which allowed DoS and stat inflation. | A per-day cap on rows per pact: gym 3, steps 20, nutrition 3. |
| A pact could promise more days than were left in the week. | `target_days` must be ≤ days left. Settlement skips pacts created after the week ended. |
| A user could stake more than they had. | Create-pact requires balance minus this week's pledges ≥ `stake × target_days`. |
| No rate limits. | In-memory fixed windows: 240 requests/min per IP across the API. OTP requests: 3 per 10 min per phone and 10 per 10 min per IP. Verify: 30 per 10 min per IP. Each code allows 5 tries and expires after 120s. |
| No body limit. | Bodies with `Content-Length` > 16 KB get 413. |
| CSRF exposure once cookies exist. | Non-GET requests with a `Sec-Fetch-Site` other than same-origin or none get 403, on top of the SameSite=Strict cookie. |
| `/docs` and `/openapi.json` were public. | They exist only in DEMO, at `/api/docs` and `/api/openapi.json`. |
| No cache or nosniff headers, no compression. | API responses get `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`. `GZipMiddleware` applies above 1 KB. |
| Demo data seeded in every environment. | Seeding runs only when `DEMO=1` and the DB is empty. Demo users get phones `09120000001` to `09120000009`, and user 1 is "you". |
| No health endpoint. | `GET /api/health` added. |
| Importing `main.py` created and seeded the DB, so tests touched real data. | `init()` moved into the FastAPI lifespan. Importing is now side-effect free. |

New environment variables: `DEMO`, `ADMIN_TOKEN`, `SMS_WEBHOOK_URL`, `COOKIE_SECURE`, `TRUST_PROXY`, `APP_TZ`, plus the existing `DB_PATH`.

- **SMS:** when `SMS_WEBHOOK_URL` is set, the backend POSTs `{"phone","code","text"}` to it.
- **No SMS in production:** with no webhook and no DEMO, login returns 503 `sms_unavailable`.
- **SMS in DEMO:** the code is logged with the phone masked, and the OTP response also returns it.

**Smoke test results.** Run with `DEMO=1`, a fresh DB, and uvicorn on :8399. All results matched expectations, and the server logged no errors.

| Probe | Result |
|---|---|
| `GET /api/health` | `{"ok":true}` |
| `GET /api/dashboard` with no cookie | 401 |
| `GET /api/business` | 200. It is public by design and returns aggregates only. |
| OTP for `۰۹۱۲۰۰۰۰۰۰۱` (Persian digits) | code returned, and the phone was normalized |
| verify with a wrong code | 400 `code` |
| verify with the right code | `{"new":false}`, and the `sid` cookie is HttpOnly |
| dashboard and check-in with the cookie | 200, real data |
| check-in on pact 5, which belongs to another user | 404 `not_found` (the IDOR attempt is blocked) |
| POST with `Sec-Fetch-Site: cross-site` | 403 `csrf` |
| 20 KB body | 413 `too_large` |
| `POST /api/settle`, then again | first call settles, second returns 409 `settled` |
| `/api/docs` in DEMO | 200, as expected. Production mode was not tested. |

The test script is easy to rebuild from the table: curl with a cookie jar against `DEMO=1 DB_PATH=/tmp/x.db .venv/bin/python -m uvicorn main:app --port 8399`.

## 4. What is NOT done, in priority order

### P0: the app is broken end-to-end until this is done

1. **Frontend login flow.** Every page now gets 401 and shows the generic error card.
   - Add a phone → OTP screen in Apple sheet style.
   - Make `useApi` and `post` in `frontend/lib/api.ts` send users to login on 401.
   - Add logout.
   - In DEMO, show or prefill the returned code.
2. **New error codes in `frontend/lib/i18n.tsx`, fa and en.** The codes are `auth`, `rate_limited`, `limit`, `days`, `balance`, `phone`, `code`, `too_large`, `csrf`, `topup_unavailable` and `sms_unavailable`. Example: `code` → «کد تایید نادرست است».
3. **Hide demo-only buttons.** Show top-up and close-the-week only when the API returns `demo: true`. Close the week also needs a confirmation step.
4. **Limit the wizard to what the API allows.** In `frontend/app/pacts/page.tsx`, offer only `days_left` options, which `/api/dashboard` now returns. Show the balance check before the hold-to-seal step.
5. **Fix the old database.** `backend/pact.db` is tracked in git, and the Docker volume `pact-data` holds an MVP-era DB. Those users have no phone, so nobody can log in as them.
   - Run `git rm --cached backend/pact.db`.
   - Add `*.db`, `*.db-wal`, `*.db-shm` and `frontend/tsconfig.tsbuildinfo` to `.gitignore`.
   - Then either delete the dev DB and the volume, or backfill phones in DEMO.

### P1: remaining security gaps, from the manual read

| # | Issue | Where | Fix |
|---|---|---|---|
| 1 | **Last-day farming.** Winners split by stake alone. On Friday a user can open a 1-day pact with a 1,000,000 stake, check in once, and take most of the pool at almost no risk. | `settle()` | Ask the owner. Options: weight shares by `stake × target_days`, or make new pacts start next Saturday. |
| 2 | Gym check-in `value` allows up to 100,000 minutes. | `CheckIn` model | Cap minutes per pact type, e.g. gym ≤ 300. |
| 3 | Behind the Next proxy every request has the frontend's IP, so all users share one 240/min bucket. | `client_ip()`, compose | Set `TRUST_PROXY=1` and stop publishing :8330, so `X-Forwarded-For` cannot be spoofed. **Not yet verified:** whether Next rewrites forward `X-Forwarded-For`. |
| 4 | Once the limiter holds more than 50k keys it clears all counters. Flooding it resets the OTP limits, which enables SMS bombing and higher SMS cost. | `limit()` | Drop only expired windows instead of clearing everything. |
| 5 | Requesting a new OTP resets the try counter. That allows about 15 guesses per 10 min per phone, roughly a 0.2% chance per day of guessing a code. | `request_otp` | Keep a per-phone daily verify cap, or don't reset `tries`. |
| 6 | The body-size check reads only `Content-Length`. Chunked bodies bypass it. | `guards` middleware | Cap at the reverse proxy or uvicorn, or read the stream with a limit. |
| 7 | Check-ins are self-reported. | product | Add GPS/QR gym verification and step sync, as the README already says. |
| 8 | FK clauses apply only to newly created tables. MVP tables keep no `REFERENCES`. | `init()` | Accept this, or rebuild the tables in a migration. |
| 9 | **Not yet verified:** whether `python:3.12-slim` ships tzdata for `ZoneInfo("Asia/Tehran")`. | backend Dockerfile | Add `tzdata` to `requirements.txt` to be safe. |
| 10 | Real deposits and withdrawals do not exist. | wallet | Payment gateway callback with signature check. Iranian options include Zarinpal and IDPay. Ask the owner. |

### P1: infrastructure (nothing done yet)

- **`docker-compose.yml`**
  - Stop publishing the backend port, or bind it to `127.0.0.1:8330`.
  - Add env: `DEMO`, `TRUST_PROXY=1`, `ADMIN_TOKEN`, `SMS_WEBHOOK_URL`.
  - Healthchecks: `/api/health` for the backend and `/` for the frontend.
  - Hardening: `read_only: true` with a tmpfs, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, memory and CPU limits.
- **`backend/Dockerfile`**
  - Run as a non-root user and `chown /data`.
  - Pin the base image by digest.
  - Add a `HEALTHCHECK`.
  - Run uvicorn with `--proxy-headers --forwarded-allow-ips=<frontend net>`.
- **`backend/requirements.txt`**
  - Pin the transitive packages. Today's versions:

    `annotated-doc==0.0.5 annotated-types==0.8.0 anyio==4.15.1 click==8.5.0 fastapi==0.141.1 h11==0.16.0 idna==3.20 pydantic==2.13.5 pydantic_core==2.46.5 starlette==1.7.0 typing_extensions==4.16.0 typing-inspection==0.4.4 uvicorn==0.53.0`

  - Ideally use `--require-hashes`.
- **`frontend/Dockerfile`**
  - It already runs as non-root `node` with the standalone build.
  - Pin `node:24-alpine` by digest.
- **`frontend/next.config.ts` security headers**
  - Set `poweredByHeader: false`.
  - Add a CSP. The inline theme script in `app/layout.tsx` needs a sha256 hash or a nonce.
  - Add `frame-ancestors 'none'` and `X-Frame-Options: DENY`, since hold-to-seal is a clickjacking target.
  - Add `nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, a `Permissions-Policy` that turns off camera, mic and geolocation for now, and HSTS once TLS is in place.
- **`lang` cookie** in `lib/i18n.tsx` `setLang`: add `SameSite=Lax`, plus `Secure` on https.

### P1: tests

- Add `backend/test_api.py` using FastAPI `TestClient`, which needs `httpx` as a dev-only dependency.
- Cover: auth required, IDOR, CSRF, the OTP try limit, rate limits, check-in caps, `days` and `balance` rules, settle idempotency, the Tehran-timezone day boundary, and DEMO-off behavior (top-up 503, settle 404, docs 404).
- Keep `test_settle.py`. It still passes.

### P2: performance (frontend; nothing done yet)

- **Fonts.** `layout.tsx` imports both variable fonts globally. The Inter files total 1.9 MB on disk, though browsers fetch only the unicode-ranges they use. Load Vazirmatn for fa and Inter for en only, e.g. with `next/font/local`, and set `font-display: swap`.
- **Always-running GPU work** in `globals.css` and `Shell.tsx`:
  - `.aurora`: three 48vmax circles with `blur(100px)`, animating forever.
  - `.mark`: the logo spins forever.
  - `backdrop-filter: blur(28px)` on every `.card`.
  - `.rise` animates `filter: blur`.
  - A global `pointermove` listener writes CSS variables on every event.
  - `CountUp` calls `setState` every frame for 1.4s.
  - Pause or reduce these, and respect `prefers-reduced-motion` and `prefers-reduced-transparency`.
- **Data fetching.** Every page is `"use client"` and fetches after mount, showing a skeleton first and then the data. `useApi` refetches on every navigation with no cache. Add a small module-level cache keyed by path, or server-render the first payload.

### P2: UI/UX following Apple's design principles (nothing done yet)

Read `~/.claude/skills/apple-design/SKILL.md` first. Concrete items:

- **Sheets.** Use spring motion and drag-to-dismiss with velocity handoff and rubber-banding, instead of CSS keyframes. Name each `<dialog>` with `aria-labelledby` and manage focus.
- **Feedback.** Respond on pointer-down. Each kind of feedback (status, completion, warning, error) needs its own visible state.
- **Media queries.** Add `prefers-reduced-transparency` (solid surfaces) and `prefers-contrast: more`. Only reduced-motion exists today.
- **Typography.** Use size-specific tracking: negative on large headings, about 0 on body. Use `rem` sizes so text scales with user settings.
- **Accessibility**
  - Status today is shown by color alone (good/bad). Add icons or text.
  - Check contrast of `--muted` on glass surfaces.
  - `HoldButton` needs an accessible name and a non-hold alternative.
  - Toasts need `aria-live`.
  - Touch targets must be ≥ 44px.
- **RTL.** The Toast centers with a translate that depends on direction; check it. Also check arrow icons and the `hold-fill` origin.
- **Wayfinding.** The "Business" B2B marketing page sits in the main user nav. Consider moving it.
- **Copy.** Audit all fa strings against `~/references/persian-ux-vocab/README.md`.

### P3: pen test after the fixes

Run `docker compose up -d --build` with production-like env (`DEMO` unset, `ADMIN_TOKEN` set). Then attack the live stack:

- Login without a code and OTP brute force.
- Session fixation and replay after logout.
- Cookie flags.
- IDOR on every `{pid}` and `{rid}`.
- CSRF from a cross-origin page.
- Spoofing `X-Forwarded-For` to dodge the rate limit.
- A chunked oversized body.
- `/api/docs` and `/api/openapi.json` must return 404.
- Admin settle without the token or with a wrong one.
- Check that the CSP and other headers are present.
- Clickjacking with an iframe.
- A race test: 50 parallel create-pact or redeem requests must not double-spend.

Then write the results down.

## 5. Open questions for the owner

1. Which pool-split rule closes the last-day farming hole? Options: stake × days, or pacts start next week.
2. Which SMS provider? The backend expects a webhook that takes `{"phone","code","text"}`.
3. Which payment gateway for real top-ups and withdrawals?
4. Should the "Business" page stay in the user app's nav?

## 6. Environment gotchas

- **Broken venv launchers.** `backend/.venv` was copied from `/home/makhataei/Documents/Darvag/Projects/30_Pact/backend/.venv`, so its scripts' shebangs point at a missing path. `.venv/bin/uvicorn` fails with "required file not found". Use `.venv/bin/python -m uvicorn ...` and `.venv/bin/python -m pip ...`, or recreate the venv.
- **Port 3000 is busy.** An unrelated `next-server` process (pid 156111 at the time) holds it. Do not kill it blindly. Dev uses :3330 and :8330.
- **Browser.** Google Chrome is at `/usr/bin/google-chrome`. The project has no Playwright.
- **Temporary scan tools.** pip-audit, bandit, semgrep, playwright and httpx were installed in this session's scratch venv. It may be gone, so reinstall them in a throwaway venv rather than the project venv.
- **graphify.** `CLAUDE.md` asks to run `graphify update .` after code changes, but this project has no `graphify-out/` yet.
- **Untracked files.** `skills-lock.json` and `frontend/tsconfig.tsbuildinfo` are untracked. Neither belongs in git.
- **Docs.** The business-plan PDFs in `Docs/` are gitignored.

## 7. Quick commands

```bash
# backend tests and dev server (note: python -m, see gotchas)
cd backend
.venv/bin/python test_settle.py
DEMO=1 DB_PATH=/tmp/dev.db .venv/bin/python -m uvicorn main:app --port 8330 --reload

# log in with the demo user (DEMO=1 returns the code)
curl -s -H content-type:application/json -d '{"phone":"09120000001"}' localhost:8330/api/auth/otp
curl -s -c jar -H content-type:application/json -d '{"phone":"09120000001","code":"<code>"}' localhost:8330/api/auth/verify
curl -s -b jar localhost:8330/api/dashboard

# frontend
cd frontend && npx tsc --noEmit && npm run build && npm run dev   # :3330, proxies /api to :8330
```
