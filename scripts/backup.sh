#!/usr/bin/env bash
# Consistent online backup of the SQLite ledger. Safe while the app runs: VACUUM INTO takes a read snapshot (WAL content included).
#   scripts/backup.sh                       -> backup-YYYYmmdd-HHMMSS.db in the current directory
#   scripts/backup.sh /safe/place/x.db
#   scripts/backup.sh - | age -r <ops-public-key> > pact.db.age     # stream to stdout (nothing readable is written to disk)
# The file holds phone numbers and balances: every copy is created owner-only (0600), the copy inside the data volume is removed
# even if streaming fails, and only a file that passed integrity_check ever gets its final name.
# Restore: see docs/OPERATIONS.md (ownership must be the app user, uid 10001).
set -euo pipefail
umask 077
out="${1:-backup-$(date +%Y%m%d-%H%M%S).db}"
tmp="$(mktemp "${TMPDIR:-/tmp}/pact-backup.XXXXXX")"   # 0600, never inside the repository
trap 'rm -f "$tmp"' EXIT
docker compose exec -T backend python -c '
import os, shutil, sqlite3, sys
os.umask(0o077)
p = "/data/.backup.db"
try:
    if os.path.exists(p): os.remove(p)
    c = sqlite3.connect("/data/pact.db"); c.execute("VACUUM INTO ?", (p,)); c.close()
    with open(p, "rb") as f: shutil.copyfileobj(f, sys.stdout.buffer)   # streamed: the DB is never held in memory
finally:
    if os.path.exists(p): os.remove(p)' > "$tmp"
python3 - "$tmp" >&2 <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "backup failed integrity_check"
print(f"integrity ok, {con.execute('SELECT COUNT(*) FROM users').fetchone()[0]} users")
PY
if [ "$out" = "-" ]; then cat "$tmp"; else mv "$tmp" "$out"; echo "backup OK: $out" >&2; fi
