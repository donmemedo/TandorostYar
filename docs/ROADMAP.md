# Roadmap, launch gates and role-review log

Everything below the first section is the record of an independent review panel (six agents, each reading the code read-only) and what was done about each suggestion. `D` done, `P` partly, `O` owner decision or external input needed, `N` declined with a reason.

## Launch gates (owner decisions, in order)

1. **Legal structure of the pool (P0, from the Product Owner).** Winners are paid from other users' missed-day stakes and a fee is taken whether or not anyone wins. That is the textbook shape of gambling (قمار/گروبندی) in the reviewer's reading, and the owner's own plan (*Docs/30-Business-plan-toolkit_Pact_Iran_filled.pdf*, pp. 3 and 23) says to use a service contract, a refundable commitment, credit rewards, and donation of failed amounts **instead of betting**, with review by a lawyer, the payment provider and a fiqh/law expert. The legal citations in the review are from general knowledge and **must be confirmed by counsel**. Until then: **no real money**. The switch exists: set `PAYOUT_CAP_X=0` and missed-day money goes to the charity after the fee, never to another user. Then rewrite the copy (tagline, «برندگان», «جریمه») to match.
2. **A real core loop before payments.** In production nobody can create a pact (top-up is demo-only). No-money pacts (stake 0) are implemented so a signup can use the product today; measure weekly retention on them before building a payment flow.
3. **Consent and age.** Required before real money: a versioned acceptance of the money terms, an 18+ confirmation, a health disclaimer, and a privacy notice. Counsel writes the text; storing `terms_version` and `accepted_at` is a small change.
4. **Pact start rule.** A pact opened after today's workout is a guaranteed win for that day. Recommended: new pacts start next Saturday after a free practice week.
5. **Check-in verification.** Self-reported check-ins are the dominant fraud channel: GPS/QR at partner gyms, wearable step sync. Scale exposure by goal difficulty once steps are synced.
6. **Recycled phone numbers** can inherit an account and its balance. Before withdrawals: idle-account re-verification (for example Shahkar) and a second factor on first withdrawal.
7. **Payment gateway** (Zarinpal, IDPay, ...) with signed callbacks, and a withdrawal flow with `withdrawable = balance − held`; **SMS provider** choice.
8. **Operations:** external uptime monitor and log shipping with the alert rules from [SECURITY.md](SECURITY.md#detection-matrix); a restore drill; encrypted off-host backups.

## Engineering backlog (not built)

- PWA, Android (APK/AAB) and iOS (IPA) builds. The web app was built first as requested; it is already PWA-ready in structure (safe-area insets, theme colours, no hover-only UI).
- A per-week `void`/hold control for settlement; a route-level test crossing Friday 23:59 to Saturday 00:00 Tehran.
- Component and browser tests in CI (the committed `scripts/e2e` scripts are the start; Playwright is the next step).
- Redis limiter and Postgres when running more than one backend process. The edge still runs as uid 0 inside its container with all capabilities dropped but `NET_BIND_SERVICE`.
- Passkeys / WebAuthn to retire SMS-OTP risk; a leaderboard opt-out; ledger rows that carry a week and pact reference.

## Review log

### Product Owner

| # | Pri | Suggestion | | What happened |
|---|---|---|---|---|
| 1 | P0 | Winners are paid from losers' stakes, which is the gambling-shaped part, and the owner's own Iran plan already rejected it | O | Launch gate. `PAYOUT_CAP_X=0` now gives charity-only mode with no other change; copy and legal structure are the owner's decision (see below). |
| 2 | P0 | In production, no user can create a pact, so the web-app-first launch has no core loop | P | No-money pacts (stake 0) now work with an empty wallet. Payments and withdrawals still need a gateway. |
| 3 | P1 | Signup records no consent to the money contract, no 18+ confirmation and no health disclaimer | O | Needs counsel's wording. The mechanism (checkbox + `terms_version`/`accepted_at`) is small once the text exists. |
| 4 | P1 | Pacts renew every week, but the wizard never says so | D | The summary step states weekly auto-renewal. |
| 5 | P1 | A pact opened after today's workout is a guaranteed win; neither exposure weighting nor GPS/QR closes this | O | Owner decision: new pacts start next Saturday after a free practice week. Not changed silently because it alters the product. |
| 6 | P1 | Auto-pause is silent: every pact disappears, the page says 'no pacts yet', and the streak resets | D | A zero-amount `paused` ledger row, a wallet entry, and a dashboard message with a link to the wallet. |
| 7 | P1 | The pool screens misstate where the money goes | D | Copy now states the 3x cap and where the remainder goes. |
| 8 | P2 | The reward store takes points and delivers nothing | D | The redeem endpoint is removed (points can no longer be burned for nothing); rewards show as coming soon. |
| 9 | P2 | The business page sells plans and features that don't exist and contradicts the app | P | Free-plan text matches the app; an explicit note says prices are illustrative. Plans themselves are still marketing copy. |
| 10 | P2 | Onboarding: a bare login wall, the new-user flag is ignored, and a random handle goes on the leaderboard | D | New users land on their profile to set a name. |
| 11 | P2 | Persian copy: the wrong error on account deletion, mixed تو/شما, and vocab slips | D | Wrong error code fixed (`has_balance`), tone made consistently informal, vocabulary slips corrected. |
| 12 | P2 | The open owner decisions are written down nowhere: the README links 7 docs that don't exist | D | This file. |

### Tech Lead

| # | Pri | Suggestion | | What happened |
|---|---|---|---|---|
| 1 | P1 | Auto-settlement trusts the wall clock and ignores downtime, and there is no hold or void control | P | Clock-jump and clock-back hold (CRITICAL log, operator release) implemented for every caller. A per-week `void` control is not built. |
| 2 | P1 | The production settlement path (settle_due and the sweeper) has zero tests | D | The real sweeper is exercised end to end: catch-up, epoch, created-after filter, cancellation, idempotency, conservation, winner payout in the ledger. |
| 3 | P1 | backup.sh stops working once the ledger passes 16 MB | D | `VACUUM INTO` inside the volume, streamed, verified before it gets its final name. |
| 4 | P2 | An SMS provider outage uses up the login budgets, so logins stay blocked after the provider recovers | D | Outage refunds the phone and global budgets; provider rejections and the IP budget are never refunded; 3-failure circuit breaker. |
| 5 | P2 | /api/community can return 500 (KeyError) for up to 5 seconds right after the weekly settlement | D | Names are looked up for exactly the snapshot's users. |
| 6 | P2 | Money invariants are enforced only in app code; add a database guard and an automatic reconciliation | D | A trigger forbids negative balances/points; the sweeper reconciles every balance against its ledger (`ledger_mismatch`). |
| 7 | P2 | Nothing shows whether weekly settlement is actually running | D | Empty weeks get a row; `week_settled` is logged inside `settle_week`; `/api/health` reports `settled_through`. |
| 8 | P3 | A pact created just after the week rolls over can be paused by the old week's settlement, and the pause leaves no trace | D | `create_pact` settles first (under the same lock); a pause stamps the pact's end date. |
| 9 | P3 | Migrations never read user_version | D | Migrations are versioned (`user_version` 1 to 4), each step runs once. |
| 10 | P3 | Error code mismatch: account deletion's 409 'balance' displays as 'Not enough balance' | D | `has_balance` has its own message; a non-JSON 5xx shows the server error. |
| 11 | P3 | Check-in runs the full week query twice under the write lock just to detect a crossed goal | D | Goal crossing is computed from the numbers already read; one `pacts_view` for the response. |
| 12 | P3 | The incident runbook's session-revocation command cannot run | D | Runbook uses the container's Python; operator levers added. |

### Red Team

| # | Pri | Suggestion | | What happened |
|---|---|---|---|---|
| 1 | P1 | The 10-per-day OTP send cap per phone never applies, because the sweeper and every successful login delete its counter | D | Fixed with a regression test (same defect as Blue #1). |
| 2 | P1 | Creating a pact still runs settlement while the clock-safety hold is on | D | The hold guard lives in `settle_due`, so every caller obeys it. |
| 3 | P2 | Per-IP limits use the full IPv6 address, and IPv6 users behind docker-proxy or a CDN all share one IP | D | IPv6 keyed by /64; IPv4-mapped collapses. |
| 4 | P2 | OTP budgets are refunded when the SMS provider rejects a number, so those numbers bypass the OTP limits | D | Provider rejections cost the caller; only real outages refund. |
| 5 | P2 | Rejected requests skip the rate limiter and log unbounded paths, so anyone can wipe the 30 MB of local logs in seconds | D | Limiter runs first; rejection logs capped at 5 per IP per minute with 200-character paths. |
| 6 | P2 | The 'hashed phone reference' in logs can be reversed to the phone number in minutes | D | Keyed HMAC references. |
| 7 | P2 | The API accepts a 1,000-step goal and payouts ignore goal difficulty, giving an almost certain win even after step sync | D | Step goal floor 6,000. Scaling exposure by goal difficulty is a product call and is listed below. |
| 8 | P2 | The public /api/business endpoint scans 14 days of check-ins on every request, with no cache | D | Public chart is served from the shared 5 s cache. |
| 9 | P2 | Supply chain: the public-facing Caddy image is never updated or scanned, CI scanners are unpinned, and gitleaks skips docs/ | D | Caddy covered by Dependabot and Trivy; scanner versions pinned; gitleaks directory exemptions removed. |
| 10 | P3 | Accounts can't sign out everywhere, and a recycled phone number takes over the old account | P | Sign out of all devices is built. A recycled phone number inheriting an account is OPEN and must be solved before withdrawals. |
| 11 | P3 | Configuration and ops shortcuts that silently weaken production | D | Plain-http SMS webhooks refused unless internal; CRITICAL log when cookies are not Secure; backups owner-only. |
| 12 | P3 | Attack tree of what is still open (red-team view; items refer to #1-#11) | D | Merged into the attack tree in SECURITY.md. |

### Blue Team

| # | Pri | Suggestion | | What happened |
|---|---|---|---|---|
| 1 | P1 | Sweeper deletes OTP rows, so the daily send cap and the guess counter are lost every 10 minutes | D | The 24 h window now survives logins and the sweeper (purged only when the window has ended). |
| 2 | P1 | The SMS-pumping and OTP alerts in SECURITY.md watch events the code never emits | D | Limiter logs the first rejection per window with `scope`; locked requests log too. |
| 3 | P1 | Detection matrix: one response is wrong, the takeover signal is missing, and the responses can't be carried out | D | Matrix rewritten: admin_denied from inside = compromise, takeover row, spray, provider outage, 5xx, liveness; levers documented. |
| 4 | P1 | No one is alerted: CRITICAL events and health checks stay on local disk | P | Compose log retention (50 MB x 20, compressed), a real edge healthcheck, external-monitor guidance. Shipping logs and paging are an ops task (documented). |
| 5 | P2 | Refunding every failed SMS removes the per-IP cap on provider calls | D | The per-IP OTP budget is not refunded; a circuit breaker bounds provider calls. |
| 6 | P2 | Frontend container can reach the backend and set any client IP | D | Two networks: the frontend cannot resolve the backend; CI asserts it. |
| 7 | P2 | Phone hashes in logs can be reversed in minutes | D | Phone references are HMAC-keyed (`LOG_KEY`). |
| 8 | P2 | Edge writes no access log, and clients can choose the request ID | D | Edge JSON access log; the edge mints the request id. |
| 9 | P2 | Account deletion keeps health notes, activity history and the OTP row | D | Deletion erases pacts, check-ins and the OTP row too. |
| 10 | P2 | Backups are world-readable and unencrypted, and the restore steps break on a fresh volume | P | Owner-only files, streamed copy, verified restore sequence. Encryption (age) is documented, not automated. |
| 11 | P2 | CI never updates or scans the Caddy image, and the container-hardening step checks nothing | D | Dependabot compose ecosystem, Trivy on the Caddy digest, CI hardening assertions. |
| 12 | P2 | Gitleaks skips all of docs/ and backend/tests/ | D | No directory exemptions; exact-pattern allowlist only. |

### QA / QC

| # | Pri | Suggestion | | What happened |
|---|---|---|---|---|
| 1 | P1 | Winner payouts, the ledger invariant and five money/points branches have no test | D | `assert_ledger` on every money test; the winner payout and ledger row are asserted. |
| 2 | P1 | Four tests cannot fail, including the only in-process double-spend test | P | The double-spend test now releases three real concurrent requests through a barrier; the sleep-based tests were rewritten to poll. |
| 3 | P1 | Fixed sleeps and wall-clock windows in the suite | D | Polling with an explicit failure instead of fixed sleeps. |
| 4 | P1 | No test crosses Friday 23:59 to Saturday 00:00 Tehran, and the weekday matrix is not in CI | P | CI runs the suite on all seven weekdays. A route-level test crossing Friday 23:59 to Saturday 00:00 is still to write. |
| 5 | P1 | Failed money writes leave the UI dead or stale, which invites double submits | P | A failed seal remounts the hold button and `exists` after a lost response counts as success. Other write paths still rely on the generic error. |
| 6 | P1 | Frontend has zero tests: the smallest valuable set | P | Three unit tests (digits) in CI, plus committed headless-Chrome and axe scripts. No component test suite yet. |
| 7 | P2 | Steps check-in may reject Persian digits, and the quick-add chips overshoot the cap | D | Steps input accepts Persian digits and separators; chips are clamped. |
| 8 | P2 | A huge pact id returns 500 and logs an ERROR traceback | D | Huge or negative ids answer 422. |
| 9 | P2 | Accessibility and RTL defects: focus lost after a wrong code, LTR hold fill, screen-reader seal unverified, emoji avatars | P | Focus is kept after a wrong code; axe reports zero violations after the contrast fix. Screen-reader passes need real devices (QA.md). |
| 10 | P2 | Ambiguous acceptance criteria that tests and support will need decided | D | Written down in QA.md. |
| 11 | P3 | pentest.py cannot be re-run within 10 minutes and leaves the tester rate-limited | D | The script reports a rate-limited IP and exits 2. |
| 12 | P1 | Prioritized manual QA checklist and device matrix | D | QA.md. |

### Ponytail (simplicity)

| # | Pri | Suggestion | | What happened |
|---|---|---|---|---|
| 1 | P1 | [shrink] Daily goal and nutrition counting are hand-written three times in money code | D | Every pact now stores its own goal; the three hand-written definitions collapsed to one column. Terms can no longer change retroactively. |
| 2 | P2 | [yagni] Delete the MVP-database migration scaffolding | N | Kept: an MVP-era `pact-data` volume may exist on your machine, and the scaffolding is what lets it boot. |
| 3 | P2 | [delete] daily_checkins is a copy-paste of snapshot's single-flight TTL cache | D | One `_cached` helper serves both. |
| 4 | P2 | [yagni] check-in note is write-only, and the 8-food picker exists only to fill it | D | Free-text note removed (never read, and it was stored health data); nutrition is one button. |
| 5 | P2 | [yagni] Rewards store spends points and delivers nothing | D | Redeem endpoint, table and UI action removed. |
| 6 | P2 | [delete] pentest.py re-asserts what pytest already proves in-process | N | Kept: the live pen test is the requested black-box evidence. Its re-run behaviour and one dead line were fixed. |
| 7 | P2 | [native] Hand-built physics bottom sheet on top of a native <dialog> | N | Kept: explicit request for apple-design fluid, interruptible motion. |
| 8 | P2 | [delete] Four decorative motion effects with no product job | N | Kept: explicit request for a 'shocking' UI. All of it honours reduced-motion and reduced-transparency. |
| 9 | P3 | [delete] Dead code: unused endpoint, three unused i18n keys, unconsumed SBOM | P | `logout-all` is now wired to the account page; three unused i18n keys removed; SBOM kept as a supply-chain deliverable. |
| 10 | P3 | [stdlib] Reinvented parsing and Starlette helpers in auth.py and security.py | P | `norm_phone` shrunk to one regex; the other helpers stay. |
| 11 | P3 | [delete] Duplicate layers and restated defaults | P | Duplicate gzip removed; explicit compose values kept as documentation. |
| 12 | P3 | [shrink] SMS circuit breaker and refund-on-503 are two answers to one problem | N | Kept: the Red and Blue teams independently asked for both a refund and a breaker. |

**Totals across 72 suggestions:** 50 done, 14 partly, 3 owner decision, 5 declined.
