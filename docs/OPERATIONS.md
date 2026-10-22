# Operations runbook

## Deploy

1. `cp .env.example .env`; set `ADMIN_TOKEN=$(openssl rand -hex 32)`, `SMS_WEBHOOK_URL`, `SITE_ADDRESS=your.domain`; leave `DEMO` unset; publish `443:443` in `docker-compose.yml`.
2. `docker compose up -d --build --wait`. All three services have healthchecks; the edge starts only after the others are healthy.
3. Check: `curl -sI https://your.domain/` shows the CSP and HSTS; `curl -s -o /dev/null -w '%{http_code}' https://your.domain/api/admin/settle -X POST` returns 404 (blocked at the edge).
4. Run `python3 scripts/pentest.py` against a **DEMO staging** copy, never production.

## Settlement

Automatic (sweeper, every 10 min, idempotent). Manual from the host, never through the public edge:

```bash
docker compose exec backend python -c "import urllib.request,os;r=urllib.request.Request('http://127.0.0.1:8000/api/admin/settle',method='POST',headers={'authorization':'Bearer '+os.environ['ADMIN_TOKEN'],'content-type':'application/json'});print(urllib.request.urlopen(r).read())"
```

## Backup and restore (the SQLite file is the ledger)

```bash
scripts/backup.sh /safe/place/pact-$(date +%F).db     # online, includes WAL content, runs integrity_check
```

Backups are owner-only (`umask 077`). Encrypt before they leave the host: `scripts/backup.sh - | age -r <ops-public-key> > pact.db.age`. Schedule it (cron every hour, keep 30 days, copy off-host). **Restore drill (do it once before launch):**

```bash
docker compose stop backend
docker compose run --rm --no-deps -T backend python -c "
import os, shutil, sys
os.umask(0o077)
for f in ('/data/pact.db-wal', '/data/pact.db-shm'):       # a stale WAL would be replayed over the restored file
    if os.path.exists(f): os.remove(f)
with open('/data/pact.db', 'wb') as out: shutil.copyfileobj(sys.stdin.buffer, out)" < restored.db
docker compose start backend                                 # then check /api/health and sign in
```

This streams the file in **as the app user**, so ownership is right without root (the containers drop all capabilities, so a root `chown` would not work). Tested on 2026-10-22: wiped the ledger on a live stack, restored from `scripts/backup.sh`, 14 of 14 ledger rows and 12 of 12 users came back and the service reported healthy. If the backup is `age`-encrypted, decrypt first: `age -d -i key.txt pact.db.age > restored.db`.
Never run `docker compose down -v` in production: it deletes the volume.

## Logs and detection

Backend logs are JSON lines on stdout (`docker compose logs backend`), rotated by Docker (10 MB × 3). Ship them to your log system. Key events and what to alert on are in [SECURITY.md](SECURITY.md#detection-matrix). Every response carries `X-Request-ID`; quote it when investigating.

## Operator levers

All run inside the backend container, which has Python but no `sqlite3` CLI. Define a helper once per shell:

```bash
q() { docker compose exec -T backend python -c "import sqlite3,sys;c=sqlite3.connect('/data/pact.db');[print(r) for r in c.execute(sys.argv[1])];c.commit()" "$1"; }
```

| Goal | Command |
|---|---|
| Revoke one user's sessions | `q "DELETE FROM sessions WHERE user_id=123"` |
| Revoke everyone | `q "DELETE FROM sessions"` |
| Ban a phone from logging in for 30 days | `q "INSERT OR REPLACE INTO otps(phone,code_hash,expires,locked_until,win_start,sent) VALUES('09120000000','',0,strftime('%s','now')+2592000,strftime('%s','now'),0)"` |
| Pause a user's pacts (ends with the week) | `q "UPDATE pacts SET active=0 WHERE user_id=123"` |
| Check the ledger | `q "SELECT u.id,u.balance,COALESCE(SUM(t.amount),0) FROM users u LEFT JOIN txns t ON t.user_id=u.id GROUP BY u.id HAVING u.balance != COALESCE(SUM(t.amount),0)"` |

## Alerting and uptime

The app logs; it does not page. Minimum viable setup: (1) an external HTTP monitor on `https://your.domain/api/health` (two failed probes = page); (2) ship `docker compose logs` of `backend` and `edge` to a log service and create the alert rules in the [detection matrix](SECURITY.md#detection-matrix); (3) keep 90 days of logs (`driver: local` keeps about 1 GB per service on the host; copy them off-host daily); (4) remember Docker **never restarts an unhealthy container**, only one that exits, so an external monitor or an orchestrator is what notices a wedge.

## Incident response (first hour)

1. **Contain**: `docker compose stop edge` (site off) or block the offending IP at the host firewall. Disable login without redeploying: unset `SMS_WEBHOOK_URL` and restart the backend (login answers 503).
2. **Preserve**: `scripts/backup.sh` and `docker compose logs --no-color > incident.log` before changing anything.
3. **Session revocation** (everyone signs in again): `docker compose exec backend python -c "import sqlite3;c=sqlite3.connect('/data/pact.db');c.execute('DELETE FROM sessions');c.commit()"`.
4. **Rotate**: `ADMIN_TOKEN`, SMS webhook credentials.
5. **Money**: settlement is idempotent and conserves money. The sweeper logs `ledger_mismatch` (CRITICAL) if any balance differs from the sum of its ledger rows, and `settlement_held` (CRITICAL) if the server clock moved. A hold is released only by an operator running the manual settlement above after checking the clock. `/api/health` shows `settled_through`, which should always be last week's Saturday or later.
6. **Report** to affected users and the regulator as required, then write the post-mortem.

## Upgrades and patching

Dependabot opens weekly PRs (pip, npm, Docker digests, Actions). CI runs the full gate (tests, Bandit, Semgrep, pip-audit, npm audit, Gitleaks, Hadolint, Trivy, the live pen-test). Merge only on green. `requirements.txt` is regenerated with `uv pip compile requirements.in --generate-hashes`.

## Known operational limits

One backend process. SQLite needs local disk (not NFS). Time zone data comes from the `tzdata` package. The sweeper runs in-process: if you ever run two backend replicas, move settlement to a single cron job first.
