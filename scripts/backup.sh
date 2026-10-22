#!/usr/bin/env bash
# Consistent online backup of the SQLite ledger. Safe while the app runs: VACUUM INTO takes a read snapshot (WAL content included).
#   scripts/backup.sh                      -> backup-YYYYmmdd-HHMMSS.db
#   scripts/backup.sh /safe/place/x.db
# The copy is made inside the data volume (the container's /tmp is a small tmpfs), streamed out, then removed.
# Encrypt before it leaves the host, e.g.:  scripts/backup.sh /dev/stdout | age -r <ops-public-key> > pact.db.age
# Restore: see docs/OPERATIONS.md (ownership must be the app user, uid 10001).
set -euo pipefail
umask 077   # the file holds phone numbers and balances: owner-only, always
out="${1:-backup-$(date +%Y%m%d-%H%M%S).db}"
tmp="$out.tmp"
trap 'rm -f "$tmp"' EXIT
docker compose exec -T backend python -c '
import os, sqlite3, sys
p = "/data/.backup.db"
if os.path.exists(p): os.remove(p)
c = sqlite3.connect("/data/pact.db")
c.execute("VACUUM INTO ?", (p,)); c.close()
import shutil; shutil.copyfileobj(open(p, "rb"), sys.stdout.buffer); os.remove(p)'  # streamed: the DB is never held in memory > "$tmp"
python3 - "$tmp" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "backup failed integrity_check"
print(f"integrity ok, {con.execute('SELECT COUNT(*) FROM users').fetchone()[0]} users")
PY
mv "$tmp" "$out"            # only a verified file ever appears under the final name
echo "backup OK: $out"
