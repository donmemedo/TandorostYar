# Graph Report - TandorostYar  (2026-10-22)

## Corpus Check
- 56 files · ~315,364 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 7, .example 1, .toml 1)

## Summary
- 589 nodes · 1420 edges · 32 communities (23 shown, 9 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 126 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c0e474a9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- ui.tsx
- test_api.py
- auth.py
- auth.tsx
- Operations runbook
- Backend (`backend/app`)
- compilerOptions
- test_domain.py
- proxy.ts
- backup.sh
- pentest.py
- e2e/package.json
- Settings
- today
- domain.py
- pacts.py
- build
- new_user
- 4. What is NOT done, in priority order
- conftest.py
- .from_env
- config.py
- login
- db.py
- sweep
- peer_ip
- e2e/README.md

## God Nodes (most connected - your core abstractions)
1. `Settings` - 53 edges
2. `db()` - 33 edges
3. `useT()` - 27 edges
4. `today()` - 25 edges
5. `settle_due()` - 19 edges
6. `week_start()` - 18 edges
7. `init()` - 17 edges
8. `compilerOptions` - 17 edges
9. `verify_otp()` - 16 edges
10. `create_pact()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `Settlement rules (`domain.settle`)` --references--> `settle()`  [INFERRED]
  docs/ARCHITECTURE.md → backend/app/domain.py
- `Time` --references--> `settle_due()`  [INFERRED]
  docs/ARCHITECTURE.md → backend/app/domain.py
- `Red Team` --references--> `settle_due()`  [INFERRED]
  docs/ROADMAP.md → backend/app/domain.py
- `Data model` --references--> `topup()`  [INFERRED]
  docs/ARCHITECTURE.md → backend/app/routes/wallet.py
- `Test inventory` --references--> `assert_ledger()`  [INFERRED]
  docs/QA.md → backend/tests/test_api.py

## Import Cycles
- None detected.

## Communities (32 total, 9 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.12
Nodes (5): create_app(), lifespan(), scheduler(), configure(), JsonFormatter

### Community 1 - "ui.tsx"
Cohesion: 0.07
Nodes (85): P2: performance (frontend; nothing done yet), Account(), Biz, Business(), Community, CommunityPage(), MEDAL, Result (+77 more)

### Community 3 - "auth.py"
Cohesion: 0.10
Nodes (16): event(), ref(), delete_account(), logout(), logout_all(), me(), NameIn, norm_phone() (+8 more)

### Community 4 - "auth.tsx"
Cohesion: 0.07
Nodes (28): dependencies, @fontsource-variable/inter, @fontsource-variable/vazirmatn, lucide-react, next, react, react-dom, devDependencies (+20 more)

### Community 5 - "Operations runbook"
Cohesion: 0.07
Nodes (29): Alerting and uptime, Backup and restore (the SQLite file is the ledger), Deploy, Incident response (first hour), Known operational limits, Logs and detection, Operations runbook, Operator levers (+21 more)

### Community 6 - "Backend (`backend/app`)"
Cohesion: 0.07
Nodes (18): Guards, respond(), wrapped_send(), _json(), Limiter, test_limiter_fails_closed_instead_of_forgetting_counters(), Architecture, Authentication flow (+10 more)

### Community 7 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib (+11 more)

### Community 8 - "test_domain.py"
Cohesion: 0.19
Nodes (12): seed(), settle(), pact(), test_charity_only_mode_pays_nobody_from_anybody_elses_stake(), test_losers_pay_and_winners_share_by_exposure(), test_money_is_conserved_for_random_weeks(), test_nobody_pays_more_than_they_hold(), test_nobody_wins_everything_after_fee_goes_to_charity() (+4 more)

### Community 14 - "pentest.py"
Cohesion: 0.07
Nodes (28): clean_name(), settlements(), P0: the app is broken end-to-end until this is done, Browser (Chrome headless) and accessibility, Live black-box (through the Docker edge): 54 / 54 passed, Method, Penetration test report, Performance (measured) (+20 more)

### Community 15 - "e2e/package.json"
Cohesion: 0.08
Nodes (20): axe-core, puppeteer-core, agg, axe, out, description, devDependencies, axe-core (+12 more)

### Community 16 - "Settings"
Cohesion: 0.15
Nodes (11): Settings, db(), current_user(), get_settings(), h(), public_user(), rename(), health() (+3 more)

### Community 17 - "today"
Cohesion: 0.19
Nodes (13): init(), settle_due(), today(), week_start(), admin_settle(), business(), community(), settle_now() (+5 more)

### Community 18 - "domain.py"
Cohesion: 0.21
Nodes (12): _cached(), daily_checkins(), done_days(), pacts_view(), pool_view(), settle_week(), snapshot(), streak() (+4 more)

### Community 19 - "pacts.py"
Cohesion: 0.15
Nodes (4): is_held(), CheckIn, end_pact(), NewPact

### Community 20 - "build"
Cohesion: 0.15
Nodes (14): build(), test_account_deletion_erases_activity_pacts_and_otp_row(), test_an_sms_outage_does_not_burn_the_login_budgets(), test_guard_rejections_are_logged_a_bounded_number_of_times(), test_log_phone_references_are_keyed_not_a_bare_hash(), test_only_the_trusted_proxy_hop_decides_the_client_ip(), test_otp_per_phone_limit_and_global_sms_budget(), test_provider_rejections_still_cost_the_caller_but_outages_do_not() (+6 more)

### Community 21 - "new_user"
Cohesion: 0.15
Nodes (13): assert_ledger(), new_user(), test_a_huge_pact_id_is_a_validation_error_not_a_500(), test_a_no_money_pact_is_possible_with_an_empty_wallet_and_settles_without_dividing_by_zero(), test_a_user_who_cannot_cover_next_week_is_paused_and_told(), test_an_easy_step_goal_cannot_be_bought_through_the_api(), test_cancelled_pact_still_pays_this_weeks_penalty_and_blocks_deletion(), test_checkin_caps_and_goal_points() (+5 more)

### Community 22 - "4. What is NOT done, in priority order"
Cohesion: 0.14
Nodes (14): 1. The task, 2. The project in one paragraph, 3.1 Baseline checks, before any change, 3.2 Multi-agent audit workflow: stopped, produced nothing, 3. What was done, 4. What is NOT done, in priority order, 5. Open questions for the owner, 6. Environment gotchas (+6 more)

### Community 23 - "conftest.py"
Cohesion: 0.21
Nodes (4): demo(), fake_today(), prod(), tmp_path()

### Community 24 - ".from_env"
Cohesion: 0.22
Nodes (7): _on(), test_admin_token_must_be_long_enough(), test_every_user_endpoint_requires_login(), test_log_key_must_be_long_enough(), test_phone_normalisation(), test_plain_http_sms_webhooks_are_refused_unless_internal(), test_sms_webhook_must_be_http()

### Community 26 - "login"
Cohesion: 0.25
Nodes (8): login(), test_community_survives_a_settlement_that_pauses_users_inside_the_snapshot_window(), test_csrf_layers(), test_display_names_reject_bidi_tricks_but_keep_zwnj(), test_idor_other_users_pacts_are_invisible(), test_leaderboard_never_exposes_phone_numbers(), test_logout_kills_the_session(), test_new_users_get_a_random_public_handle_not_their_phone()

### Community 27 - "db.py"
Cohesion: 0.38
Nodes (3): _add_columns(), migrate(), _script()

### Community 28 - "sweep"
Cohesion: 0.40
Nodes (4): sweep(), test_only_a_finished_daily_window_is_purged(), test_the_daily_otp_send_cap_survives_logins_and_the_sweeper(), test_wall_clock_moving_backwards_also_holds()

### Community 29 - "peer_ip"
Cohesion: 0.40
Nodes (3): _net(), peer_ip(), test_ipv6_clients_are_keyed_by_subscriber_not_by_address()

## Knowledge Gaps
- **7 isolated node(s):** `@tailwindcss/postcss`, `@types/node`, `@types/react`, `@types/react-dom`, `tailwindcss` (+2 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 239 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Second round: independent review panel` connect `build` to `today`, `sweep`, `peer_ip`, `ui.tsx`?**
  _High betweenness centrality (0.236) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `Settings` (e.g. with `init()` and `current_user()`) actually correct?**
  _`Settings` has 31 INFERRED edges - model-reasoned connections that need verification._
- **What connects `@tailwindcss/postcss`, `@types/node`, `@types/react` to the rest of the system?**
  _7 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11965811965811966 - nodes in this community are weakly interconnected._
- **Why does `HoldButton()` connect `ui.tsx` to `build`, `4. What is NOT done, in priority order`?**
  _High betweenness centrality (0.228) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `settle_due()` (e.g. with `Time` and `3.3 Backend rewrite: `backend/main.py`, uncommitted, smoke-tested`) actually correct?**
  _`settle_due()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `ui.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.0698289543290425 - nodes in this community are weakly interconnected._