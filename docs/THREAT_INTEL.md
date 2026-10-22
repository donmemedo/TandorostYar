# Threat-intelligence lifecycle for FitPeyman

A small-team version of the six-stage intelligence cycle, scoped to what can actually hurt this product: money abuse, account takeover, SMS-cost fraud, and vulnerable dependencies.

| Stage | What we do | Owner | Cadence |
|---|---|---|---|
| **1. Direction** | Priority intelligence requirements (PIRs): (a) new vulnerabilities in FastAPI, Starlette, uvicorn, pydantic, Next.js, React, Caddy, SQLite, Python and Node base images; (b) SMS-pumping and OTP-abuse campaigns against Iranian providers; (c) fraud patterns on stake-and-pool or fitness apps (fake check-ins, multi-accounting); (d) credential/data leaks mentioning our brand or domain. | Tech Lead | Reviewed quarterly |
| **2. Collection** | Dependabot (pip, npm, Docker, Actions); `pip-audit` and `npm audit` in CI; GitHub Security Advisories and OSV; CISA KEV for actively exploited CVEs; Trivy on images; Gitleaks on every push; the app's own logs (see the detection matrix); the SMS provider's abuse reports. | Automation + on-call | Continuous; CI weekly cron |
| **3. Processing** | Normalise to one record: component, version in our lockfile, CVE/GHSA, fixed version, exploited-in-the-wild flag. Drop anything that does not touch a package we ship (`pip-audit` and `npm audit` already do this against the lockfiles). | On-call | Per alert |
| **4. Analysis** | Score by exposure, not CVSS alone: *is the vulnerable code reachable from the internet through our edge?* (e.g. Next.js Image Optimisation SSRF is moot because images are unoptimised and `/_next/image` is switched off). Map to the attack tree in [SECURITY.md](SECURITY.md). Decide: patch now, patch this sprint, accept with a note. | Tech Lead | Within 1 business day for KEV or reachable High/Critical |
| **5. Dissemination** | A PR with the lockfile bump and a one-line risk note; for accepted risks, an entry in [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md). Incidents go to the owner and, if users are affected, to users and the regulator. | Tech Lead | Same day |
| **6. Feedback** | After each incident or near-miss: add a regression test or a pen-test check, adjust a detection threshold, update the PIRs. The live pen-test script is the memory of past findings. | Team | After every incident; retrospective quarterly |

## Indicators we track locally

`otp_locked` and `login_failed` bursts per phone reference; `rate_limited` by IP; `otp_sent` per hour against the SMS budget; `admin_denied`; `csrf_blocked`; settlement totals that fail the conservation check; accounts created per IP per day. Thresholds are in the detection matrix in [SECURITY.md](SECURITY.md#detection-matrix).

## Recent examples this cycle

- Next.js 16.3.6 carried six advisories (cache poisoning, SSRF in image optimisation, information disclosure). Collected by `npm audit`, analysed as reachable, patched to 16.4.0 the same day. Zero advisories remain.
- `sharp` and `source-map-js` advisories came in transitively; resolved by the same lockfile update.
- uvicorn's default proxy-header handling was found by our own pen test, not by a feed: it became the `python -m app` entry point and a regression test, which is the feedback loop working.
