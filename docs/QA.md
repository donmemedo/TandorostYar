# QA plan

## Test inventory

| Layer | What | Where | Run |
|---|---|---|---|
| Unit | Settlement math: conservation on 500 random weeks, balance cap, payout cap, charity-only mode, zero-weight winners, Tehran midnight | `backend/tests/test_domain.py` | `pytest` |
| Integration | 70+ API tests: one regression test per fixed finding, the production settlement path (the real sweeper), clock hold, SMS outage/rejection/breaker, concurrency (3 real simultaneous requests), ledger invariant on every money test | `backend/tests/test_api.py` | `pytest` |
| Time | The whole suite on each weekday via `FAKE_TODAY` (week-position bugs hide on specific days); CI runs all seven | `conftest.py`, CI matrix | `FAKE_TODAY=2026-10-22 pytest` |
| Frontend unit | Digit parsing (Persian/Arabic keyboards, separators, caps) | `frontend/lib/digits.test.ts` | `npm test` |
| Black-box | 54 checks against the live stack through the real edge | `scripts/pentest.py` | `python3 scripts/pentest.py URL` |
| Browser | Sign-in, every page, fa/en x light/dark x phone/desktop, sheet gestures, console and CSP errors | `scripts/e2e` | see its README |
| Accessibility | axe-core WCAG 2.x A/AA on every page and theme | `scripts/e2e` | `npm run a11y` |
| Static | Bandit, Semgrep, pip-audit, npm audit, Gitleaks, Hadolint, Trivy | CI | `.github/workflows/security.yml` |

Latest local results are in [PENTEST_REPORT.md](PENTEST_REPORT.md). Tests that move money call `assert_ledger`, the same invariant the sweeper alarms on: every balance equals the sum of its ledger rows and nothing is negative.

## Acceptance criteria that were ambiguous (decisions)

- **Day attribution.** A check-in counts for the Tehran calendar date at which the server commits it. A request sent at 23:59:59 and received at 00:00:01 counts for the next day. There is no back-fill.
- **Settlement lag.** A week ends Friday 24:00 Tehran. Money moves at the next sweep (up to 10 minutes later) or when the next user creates a pact, whichever comes first. Check-ins after Friday 24:00 belong to the new week.
- **Closed weeks are immutable.** After settlement, check-ins and new pacts for that week answer 409.
- **Cancellation** takes effect when the current week closes; this week's missed days are still charged. Account deletion is refused while any pact is active, and (outside DEMO) while a balance remains.
- **Pause.** If a user's balance cannot cover next week's full exposure, all their pacts are paused at settlement; a ledger row and a dashboard message say so. They can create new pacts after adding funds.
- **Payout.** Winners share the pool after the 12 % fee by exposure, capped at `PAYOUT_CAP_X` times their own exposure; the remainder goes to charity. With `PAYOUT_CAP_X=0`, nobody is paid from another user's stake.
- **A pact's terms are fixed at creation**, including its daily goal.

## Manual QA checklist (pre-release gate)

Run on a DEMO staging stack, never production. Restart the backend between passes: the limiter lives in memory. Record pass/fail per device in the release notes.


**P0, money and blocking:**

1. Seal a pact with each input: mouse hold, touch hold, keyboard Enter and Space, VoiceOver double-tap (iOS Safari), TalkBack double-tap (Android Chrome). Exactly one pact is created, and the available balance drops by stake x days.
2. Seal with the network cut at the moment of release (DevTools offline or airplane mode). The error appears, holding again works, and exactly one pact exists once the network is back.
3. Double-tap or double-Enter on check-in Save, End pact, Close week (demo) and Delete account. Each takes effect once, and the ledger rows match.
4. Friday 23:57 to 00:03 Tehran time (FAKE_TODAY on staging, or a real Friday night). A check-in before midnight counts for Friday, one after counts for Saturday, and the week strip resets. Within 10 min the wallet shows the reward or penalty row, and Today, Wallet and Account show the same balance.
5. Device time zone set to something other than Tehran (UTC, Los Angeles, Dubai). Week days, the 'today' highlight and Persian-calendar dates still follow Tehran.
6. Balance edges: available balance exactly equal to stake x days is allowed, and 1 Toman less disables the chip. A user paused at settlement sees the paused message and the wallet row.
7. Cancel a pact mid-week: it is still charged this week and gone next week. Account deletion is refused while a pact is active.

**P1, input, i18n and auth:**

8. OTP with Persian digits, Arabic digits, a pasted '+98 912 ...' and iOS SMS autofill. A wrong code shows «نادرست» and focus returns to the field. Five wrong codes lock for 15 min. The resend timer and changing the number both work.
9. Steps entry on Persian keyboards (Gboard فارسی, Samsung, iOS with the Persian region, Windows Persian layout). Paste '۸٬۰۰۰'. The 40,000 cap holds, including via the chips.
10. Session expires mid-flow (delete the sessions row): the app returns to sign-in, keeps the language, and Back shows no cached private data.
11. Switch fa/en on every page. Direction flips, arrows and chevrons mirror, the hold fill grows in reading direction, digits are Persian in fa, phone numbers stay left-to-right, and nothing truncates mid-word.
12. Display names: a long Persian name with ZWNJ, an emoji as the first character, a 30-character name. The leaderboard and avatar render correctly, and a bidi-override name is refused.

**P1, accessibility:**

13. Keyboard only. The skip link works, the focus ring is visible on glass and cards, focus stays inside sheets, Esc closes a sheet and focus returns to its trigger, and every wizard step is reachable.
14. Screen readers (VoiceOver on iOS and macOS, TalkBack, NVDA with Firefox). Each page has an h1, the nav marks the current page, toasts and Success are announced, the rings have a label, the week strip announces done days, leaderboard ranks 1-3 are read, and errors are announced as alerts.
15. Contrast: run axe or Lighthouse on every page in light and dark, and with 'Increase contrast'. In Windows forced-colors (high contrast) mode, the hold progress, pressed chips and the active tab stay visible.
16. Reduced motion and reduced transparency: no count-up, ring or spring animations, sealing still works, and cards are solid.
17. 200% zoom, Android font scale 1.3 and 320 px width. The 7-day grids, chips, bottom nav labels and wallet card are not clipped, and there is no horizontal scroll.

**P2, network:**

18. Slow 3G and a flaky VPN (common in Iran). The skeleton appears and then data, the retry card works, nothing spins forever, and a stale cached page refreshes.
19. With DEMO off, top-up and close-week are hidden and the business page works while signed out.

**Device matrix.** Android 10-14 with Chrome, Samsung Internet and Firefox, including one phone with 2-3 GB of RAM. iOS 15.x and 16.3 Safari: these lack Fetch Metadata, so writes rely on the Origin fallback; confirm sign-in, check-in and seal work. iOS 17 and 18 Safari. Windows 10/11 with Chrome, Edge and Firefox on the Persian layout. macOS Safari. Widths 320, 390, 768, 1024 and 1440. Every combination in fa and en, light and dark.

## Known gaps

- No component-level or full browser test suite in CI yet (Playwright is the next step; `scripts/e2e` is the seed).
- Screen-reader behaviour (VoiceOver, TalkBack, NVDA) needs real devices: items 14 and 1 above.
- iOS 15 and 16.3 Safari lack Fetch Metadata, so writes rely on the Origin fallback: verify on a real device.
- No load test beyond the hot-query benchmark in [ARCHITECTURE.md](ARCHITECTURE.md#performance-design).
