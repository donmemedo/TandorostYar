# End-to-end and accessibility checks

Dev tooling (not part of the app). Needs a **DEMO** stack running (the scripts sign in with the demo codes) and Chrome.

```bash
cd scripts/e2e && npm install
BASE_URL=http://127.0.0.1:3330 OUT=../../docs/screenshots npm run e2e   # sign in, every page, fa/en x light/dark x phone/desktop, sheet gestures, perf snapshot
BASE_URL=http://127.0.0.1:3330 npm run a11y                              # axe-core WCAG 2.x A/AA + best practices on every page
```

`CHROME=/path/to/chrome` overrides the browser. The server rate-limits OTP requests (3 per phone and 10 per IP per 10 minutes), so the scripts rotate demo phones; restart the backend between runs: `docker compose restart backend`.
`e2e` prints JSON: whether each viewport overflowed horizontally, whether the sheet dragged away / sprang back / closed on Esc, first-paint, requests, fonts, and 5 seconds of idle CPU. Console errors and CSP violations are listed under `problems` (expect only the signed-out 401 and aborted route prefetches).
