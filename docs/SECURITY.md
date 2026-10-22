# Security

How FitPeyman is defended, what an attacker would try, how we would notice, and what is still open. Evidence for every claim is in [PENTEST_REPORT.md](PENTEST_REPORT.md) and the tests; the 63 audit findings are in [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md).

## Assets and trust boundaries

| Asset | Why it matters | Where it lives |
|---|---|---|
| Money: balances, stakes, the weekly pool | Direct financial loss and legal exposure | `users.balance`, `txns`, `settlements` in SQLite |
| Phone numbers and sessions | Account takeover, privacy | `users.phone`, `sessions` (only `sha256(token)` stored) |
| SMS budget | Every OTP costs real money | provider account, `SMS_HOURLY_BUDGET` |
| Availability of weekly settlement | Wrong or missing settlement is a money bug | sweeper thread, `settlements` |

Boundary 1: internet to **edge** (Caddy). Boundary 2: edge to backend/frontend (private compose network; only the edge publishes a port). Boundary 3: backend to SMS provider (outbound only).

## Controls

| Area | Control | Where |
|---|---|---|
| Login | Phone + 6-digit code, 120 s expiry, single use, SHA-256 of `phone:code` stored; constant-time compare; 5 wrong guesses lock the phone for 15 min and a resend does not refill them; **10 sends per phone per 24 h (the window outlives logins and the sweeper)**; 3 per 10 min/phone; 10 per 10 min/IP; **global** hourly SMS budget. A provider *outage* refunds the phone and global budgets (not the IP's); a provider *rejection* of a number refunds nothing; 3 straight failures open a 60 s circuit breaker | `routes/auth.py` |
| Sessions | 256-bit random token, only its hash stored; `__Host-sid` cookie (Secure, HttpOnly, SameSite=Strict, Path=/, no Domain); 30-day absolute expiry; max 5 sessions per user; logout deletes server-side; **sign out of all devices** (`/api/auth/logout-all`); expired rows purged | `routes/auth.py`, `main.sweep` |
| Request guard | Pure-ASGI. The per-IP limiter runs **first**, so rejected requests spend budget too; then the streaming 16 KB body cap (chunked too) and CSRF (Fetch Metadata, else Origin, plus a JSON content type that cross-site forms cannot send). Rejections are logged at most 5 per IP per minute with a 200-character path, so a flood cannot scroll evidence out of the logs. Request ids, no-store + locked-down CSP on every API response | `security.py` |
| Client IP | Only the Nth-from-right `X-Forwarded-For` entry appended by the trusted edge; the leftmost is never believed; IPv6 clients are keyed by /64 and IPv4-mapped addresses collapse; `python -m app` stops uvicorn rewriting it | `security.peer_ip`, `__main__.py`, `edge/Caddyfile` |
| Rate limiter | Fixed windows, bounded memory, fail-closed for new keys when full (an attacker cannot reset counters by flooding) | `security.Limiter` |
| Authorisation | Every user endpoint depends on `current_user`; every row access is scoped by `user_id`; other users' pacts answer 404 (no existence oracle) | `deps.py`, `routes/` |
| Money | Reads and writes inside one `BEGIN IMMEDIATE` transaction; balances re-read under the lock; closed weeks are immutable; settlement idempotent (`settlements.week` PK); nobody pays more than they hold; a trigger forbids negative balances/points; the sweeper reconciles every balance with its ledger rows | `db.py`, `domain.py`, `main.sweep` |
| Settlement integrity | Settles only completed weeks since the ledger epoch; **holds** and logs CRITICAL if the wall clock moves back or jumps (the guard is in `settle_due`, so `create_pact`, the sweeper and every other caller obey it); released only by an operator. Config refuses plain-http SMS webhooks to public hosts and warns CRITICAL when cookies are not Secure outside DEMO | `main.sweep` |
| Input | Pydantic bounds everywhere; validation errors never echo input; ASCII-digit phones; display names reject bidi/zero-width characters (ZWNJ allowed) | `routes/`, `auth.clean_name` |
| Browser | Per-request nonce CSP (`script-src 'self' 'nonce-…' 'strict-dynamic'`, `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'none'`), `X-Frame-Options`, nosniff, Referrer-Policy, Permissions-Policy, COOP; HSTS at the edge on HTTPS; image optimiser (an SSRF surface) switched off; no `dangerouslySetInnerHTML` except the nonced theme bootstrap | `frontend/proxy.ts`, `next.config.ts`, `edge/Caddyfile` |
| Privacy | Leaderboard shows display names only; default names are random, never phone-derived; logs carry a **keyed** (HMAC, `LOG_KEY`) phone reference, not a bare hash; `DELETE /api/me` erases phone, name, sessions, pacts, check-ins (incl. free-text notes) and the OTP row, keeping only anonymised ledger rows | `routes/auth.py`, `obs.py` |
| Containers | Non-root backend/frontend, read-only root filesystem, all capabilities dropped, `no-new-privileges`, pid/memory/CPU limits, healthchecks (edge included), rotated logs; backend and frontend not published; **two networks so the frontend cannot reach the backend**; edge JSON access log and edge-minted request ids; base images pinned by digest; dependencies hash-locked | `docker-compose.yml`, Dockerfiles |
| Pipeline | Tests, Bandit, Semgrep (versions pinned), pip-audit, npm audit, Gitleaks (no directory exemptions), Hadolint, Trivy on the app images **and the Caddy edge**, SBOM, live pen test, **hardening assertions that fail the build if read-only, cap-drop, non-root, unpublished ports or network isolation regress**; actions pinned by SHA; Dependabot incl. compose | `.github/` |

## Attack tree

Goal-oriented, AND/OR. Cost/skill are an estimate for the attacker; **Det** is how we would notice (see the matrix below).

```
G1  STEAL MONEY FROM THE POOL  (OR)
├─ 1.1 Win without doing the activity: fake check-ins                  cost low   skill low    Det: weak (no signal)   OPEN: self-reported; verification is next
│   └─ 1.1.1 Open a 1-day max-stake pact after today's workout        cost low   skill low    Det: none               MITIGATED: exposure weighting + 3x payout cap; OWNER: pacts should start tomorrow
├─ 1.2 Double-spend a balance across concurrent requests               cost low   skill med    Det: —                  CLOSED: balance re-read under the write lock (live race test)
├─ 1.3 Push balance negative so winners are paid from nothing          cost low   skill low    Det: ledger_mismatch    CLOSED: loss capped at balance + DB trigger + reconciliation
├─ 1.4 Re-settle or settle early                                        cost med   skill med    Det: settlement_held    CLOSED: idempotent; completed weeks only; clock hold
└─ 1.5 Mint balance (top-up/admin)                                      cost med   skill med    Det: admin_denied       CLOSED: top-up demo-only; admin needs a 32+ char token and is blocked at the edge

G2  TAKE OVER ANOTHER USER'S ACCOUNT  (OR)
├─ 2.1 Brute-force the 6-digit code                                    cost med   skill low    Det: otp_locked         CLOSED: 5 guesses then a 15 min lock; resend does not reset; ~480 guesses/day/phone (0.05 %); the 24 h send cap now really applies
├─ 2.2 Steal or fixate a session                                        cost high  skill med    Det: —                  CLOSED: HttpOnly, __Host-, Strict, token hashed, logout and sign-out-everywhere revoke
├─ 2.3 CSRF a logged-in user                                            cost low   skill low    Det: csrf_blocked       CLOSED: three independent layers
├─ 2.4 SIM-swap / intercept the SMS                                     cost high  skill high   Det: none               ACCEPTED: inherent to SMS OTP; passkeys are the roadmap answer
├─ 2.5 A recycled phone number inherits the old account and balance    cost low   skill none   Det: none               OPEN: must be closed before withdrawals exist (idle-account re-verification, e.g. Shahkar)
└─ 2.6 DEMO mode reaches production (code echoed)                       cost low   skill low    Det: demo_mode_on       MITIGATED: off by default, CRITICAL log at boot; never set it

G3  DENY SERVICE / RUN UP SMS COST / HIDE  (OR)
├─ 3.1 SMS pumping through /api/auth/otp                                cost low   skill low    Det: rate_limited(scope), 429s   MITIGATED: per-phone, per-IP, 24 h cap, global hourly budget (alert on it); provider-rejected numbers still cost the caller
├─ 3.2 Lock a victim out (1 SMS + 5 wrong codes every 15 min)           cost low   skill low    Det: login_failed       ACCEPTED, but note it is a payout lever: lock a rival out of check-ins until Friday. Long sessions mean most active users are signed in; see ROADMAP
├─ 3.3 Spoof or multiply client IPs                                      cost low   skill low    Det: —                  CLOSED: trusted-hop IP, IPv6 /64 keying, uvicorn rewriting disabled; live-tested
├─ 3.4 Oversized / chunked / slow bodies                                cost low   skill low    Det: body_too_large     CLOSED: streaming cap, edge 16 KB cap, read timeouts, concurrency limit
├─ 3.5 Exhaust the thread pool via a slow SMS provider                  cost med   skill low    Det: sms_failed         MITIGATED: 5 s timeout, global budget, circuit breaker, outage refunds exclude the IP budget
├─ 3.6 Uncached public endpoint scan (/api/business)                    cost low   skill low    Det: 5xx / latency      CLOSED: shared 5 s single-flight cache for the pool, board and chart
└─ 3.7 Scroll the evidence out of the logs with cheap rejected requests cost low   skill low    Det: —                  CLOSED: limiter first, logs throttled to 5/IP/min with truncated paths, 50 MB x 20 retention; ship logs off-host

G4  EXFILTRATE USER DATA  (OR)
├─ 4.1 Read the database file (git history, volume, backups)            cost med   skill med    Det: —                  PARTLY: pact.db untracked but in history (demo data only); backups are owner-only and should be encrypted (age)
├─ 4.2 Reverse log phone references to phone numbers                    cost low   skill low    Det: —                  CLOSED: keyed HMAC (LOG_KEY); an unkeyed hash falls to a laptop in minutes
├─ 4.3 Scrape the leaderboard / business endpoint                       cost low   skill low    Det: request volume     ACCEPTED: display names only; aggregates; rate-limited
├─ 4.4 IDOR on pacts/wallet                                             cost low   skill low    Det: —                  CLOSED: row scoping, 404s
├─ 4.5 XSS to steal data                                                cost med   skill med    Det: —                  CLOSED: nonce CSP, React escaping, no HTML sinks
└─ 4.6 Pivot from a compromised frontend container to the backend        cost high  skill high   Det: —                  CLOSED: separate networks; the frontend cannot resolve the backend

G5  SUPPLY CHAIN  (OR)
├─ 5.1 Poisoned dependency                                              cost med   skill high   Det: CI                 MITIGATED: hash-locked pip, npm lockfile, audits, Dependabot
├─ 5.2 Stale internet-facing edge image                                 cost low   skill med    Det: CI                 CLOSED: digest pinned, Dependabot compose ecosystem, Trivy scans it
└─ 5.3 Hijacked CI scanner                                              cost med   skill high   Det: —                  MITIGATED: Actions pinned by SHA; bandit/pip-audit/semgrep pinned by version
```

## Detection matrix

Backend events are JSON lines on stdout with a request id (`rid`, minted by the edge); the edge writes its own JSON access log. Phone numbers appear only as a keyed 16-character reference. **Nothing pages anyone by itself**: a log pipeline and alert rules are an ops task ([OPERATIONS.md](OPERATIONS.md#alerting-and-uptime)); this table is the spec for them.

| Attack | Signal | Suggested alert | First response |
|---|---|---|---|
| OTP brute force | `login_failed` (`why=code`), `otp_locked` | ≥ 3 `otp_locked` per hour, or ≥ 20 `login_failed` per minute | Block the source at the host firewall; check the phone reference; the lock already stops that phone |
| **Account-takeover attempt that worked** | `login_ok` (`new=false`) shortly after `otp_locked` or several `login_failed` for the same phone reference | any | Revoke that user's sessions (lever below); contact the user out of band |
| Distributed spray (one IP, many phones) | many `otp_sent` for different references from one `ip`; `rate_limited scope=otp-ip` | > 5 distinct references per IP per hour | Block the IP; consider CAPTCHA |
| SMS pumping / bombing | `otp_sent` volume; `rate_limited` with `scope` `otp-ip`, `otp`, `sms-global` (logged once per window); `otp_request_while_locked` | `otp_sent` > 60 % of `SMS_HOURLY_BUDGET` in an hour; any `scope=sms-global` | Page; if confirmed, unset `SMS_WEBHOOK_URL` (login answers 503) and block IPs |
| SMS provider outage or key suspended | `sms_failed` (ERROR), `sms_rejected` (WARNING) | ≥ 3 `sms_failed` in 5 min (the breaker opens); a burst of `sms_rejected` | Check the provider; a burst of rejections is a pumping probe |
| CSRF / cross-site abuse | `csrf_blocked` | any in production (real browsers send same-origin) | Check for a frontend regression or a hostile page |
| Rate-limit evasion / flooding | `rate_limited scope=global` (with `ip`), `body_too_large`, edge access log 429/413 | first event per IP per minute | Block at the host firewall |
| **Admin probing from inside** | `admin_denied` | **any**: the edge answers 404 to `/api/admin/*`, so an `admin_denied` came from inside the compose network or the host | Treat as a **compromise**: rotate `ADMIN_TOKEN`, inspect the frontend container, review recent deploys |
| Admin probing from outside | edge access log: 404 on `/api/admin/*` | > 20 per hour | Informational; block repeat scanners |
| Ledger tampering or bug | `ledger_mismatch` (CRITICAL) | any | Freeze writes, `scripts/backup.sh`, diff `txns` against balances |
| Clock manipulation | `settlement_held` (CRITICAL) | any | Fix the clock, then release with the manual settlement |
| Settlement stalled | `sweep_failed`; `/api/health` `settled_through` older than last week's Saturday | any `sweep_failed`; stale value > 30 min after Saturday 00:30 | Read the traceback, run the manual settlement |
| Service down / wedged | `/api/health` non-200 or slow; container `unhealthy` (Docker does **not** restart unhealthy containers) | 2 failed probes from an external monitor | Restart the service; investigate |
| 5xx spike | backend `unhandled` (ERROR); edge 5xx | > 5 per minute | Read the traceback |
| DEMO or insecure config in production | `demo_mode_on`, `insecure_cookies` (CRITICAL), `log_key_unset` (WARNING) | any in a production environment | Stop and fix before serving traffic |
| Mass signup | `login_ok` with `new=true` per IP | > 5 per IP per day | Review; consider CAPTCHA or invite-only |

Operator levers that need no code change (run inside the backend container, see [OPERATIONS.md](OPERATIONS.md#operator-levers)): revoke one user's sessions, ban a phone from logging in, pause a user's pacts.

## Owner decisions that change risk

1. **Pool rule.** Exposure weighting with a 3× payout cap is implemented; it bounds but does not remove last-day farming. The stronger fix is that new pacts start the *next* day.
2. **Verification.** Self-reported check-ins are the dominant fraud channel. GPS/QR at partner gyms and wearable step sync are the real answer.
3. **Legal.** A stake-and-pool model paid out to winners can look like gambling under Iranian law; get legal review before any real money moves (see [ROADMAP.md](ROADMAP.md)).
4. **Passkeys / second factor** to retire SMS-OTP risk.

## Reporting a vulnerability

Email the repository owner privately; do not open a public issue. Please include the request id from the response and steps to reproduce.
