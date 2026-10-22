# Graph Report - TandorostYar  (2026-10-22)

## Corpus Check
- 46 files · ~300,486 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 7, .example 1, .toml 1)

## Summary
- 457 nodes · 1126 edges · 14 communities (9 shown, 5 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 78 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1adc09dd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Settings
- ui.tsx
- test_api.py
- auth.py
- auth.tsx
- 4. What is NOT done, in priority order
- Backend (`backend/app`)
- compilerOptions
- test_domain.py
- proxy.ts
- backup.sh

## God Nodes (most connected - your core abstractions)
1. `Settings` - 48 edges
2. `db()` - 30 edges
3. `useT()` - 27 edges
4. `today()` - 22 edges
5. `week_start()` - 16 edges
6. `verify_otp()` - 16 edges
7. `css()` - 16 edges
8. `compilerOptions` - 16 edges
9. `request_otp()` - 15 edges
10. `Pacts()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `Settlement rules (`domain.settle`)` --references--> `settle()`  [INFERRED]
  docs/ARCHITECTURE.md → backend/app/domain.py
- `Performance design` --references--> `pacts_view()`  [INFERRED]
  docs/ARCHITECTURE.md → backend/app/domain.py
- `P2: UI/UX following Apple's design principles (nothing done yet)` --references--> `HoldButton()`  [INFERRED]
  docs/HANDOFF.md → frontend/components/ui.tsx
- `Backend (`backend/app`)` --references--> `Settings`  [INFERRED]
  docs/ARCHITECTURE.md → backend/app/config.py
- `P1: remaining security gaps, from the manual read` --references--> `settle()`  [INFERRED]
  docs/HANDOFF.md → backend/app/domain.py

## Import Cycles
- None detected.

## Communities (14 total, 5 thin omitted)

### Community 0 - "Settings"
Cohesion: 0.06
Nodes (37): Settings, db(), init(), migrate(), _script(), current_user(), get_settings(), done_days() (+29 more)

### Community 1 - "ui.tsx"
Cohesion: 0.09
Nodes (71): P2: performance (frontend; nothing done yet), Account(), Biz, Business(), Community, CommunityPage(), MEDAL, Result (+63 more)

### Community 2 - "test_api.py"
Cohesion: 0.05
Nodes (28): _on(), build(), demo(), fake_today(), login(), prod(), tmp_path(), new_user() (+20 more)

### Community 3 - "auth.py"
Cohesion: 0.06
Nodes (25): h(), configure(), event(), JsonFormatter, ref(), clean_name(), delete_account(), logout() (+17 more)

### Community 4 - "auth.tsx"
Cohesion: 0.05
Nodes (41): metadata, RootLayout(), viewport, clearCache(), setUnauthorizedHandler(), AuthCtx, AuthProvider(), Ctx (+33 more)

### Community 5 - "4. What is NOT done, in priority order"
Cohesion: 0.06
Nodes (32): Audit register, 1. The task, 2. The project in one paragraph, 3.1 Baseline checks, before any change, 3.2 Multi-agent audit workflow: stopped, produced nothing, 3. What was done, 4. What is NOT done, in priority order, 5. Open questions for the owner (+24 more)

### Community 6 - "Backend (`backend/app`)"
Cohesion: 0.08
Nodes (19): respond(), wrapped_send(), _json(), Limiter, peer_ip(), test_limiter_fails_closed_instead_of_forgetting_counters(), Architecture, Authentication flow (+11 more)

### Community 7 - "compilerOptions"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 8 - "test_domain.py"
Cohesion: 0.19
Nodes (10): seed(), settle(), pact(), test_losers_pay_and_winners_share_by_exposure(), test_money_is_conserved_for_random_weeks(), test_nobody_pays_more_than_they_hold(), test_nobody_wins_everything_after_fee_goes_to_charity(), test_payout_is_capped_at_three_times_own_exposure() (+2 more)

## Knowledge Gaps
- **6 isolated node(s):** `@tailwindcss/postcss`, `@types/node`, `@types/react`, `@types/react-dom`, `tailwindcss` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 188 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `P0: the app is broken end-to-end until this is done` connect `auth.py` to `ui.tsx`, `4. What is NOT done, in priority order`?**
  _High betweenness centrality (0.288) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `Settings` (e.g. with `init()` and `current_user()`) actually correct?**
  _`Settings` has 29 INFERRED edges - model-reasoned connections that need verification._
- **What connects `@tailwindcss/postcss`, `@types/node`, `@types/react` to the rest of the system?**
  _6 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Settings` be split into smaller, more focused modules?**
  _Cohesion score 0.06118421052631579 - nodes in this community are weakly interconnected._
- **Why does `4. What is NOT done, in priority order` connect `4. What is NOT done, in priority order` to `Settings`, `ui.tsx`, `auth.py`?**
  _High betweenness centrality (0.215) - this node is a cross-community bridge._
- **Should `ui.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.093296853625171 - nodes in this community are weakly interconnected._
- **Should `test_api.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05143191116306254 - nodes in this community are weakly interconnected._