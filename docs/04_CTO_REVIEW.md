# 04 — CTO Brutally-Honest Review

> Part of the **RankSpy Project Bible**. See [INDEX.md](./INDEX.md).
> Reviewed as CTO for a **paid SaaS whose #1 promise is data quality**. Prioritized by **ROI & business impact, not technical interest.** Every item is grounded in the actual code.

**Effort key:** S = <1 day · M = 1–3 days · L = 1–2 weeks · XL = 3+ weeks.
**Priority:** 🟥 Critical · 🟧 High · 🟨 Medium · 🟩 Low.

---

## The three things that actually matter

Before the itemized list, the honest big picture. RankSpy has more built than most pre-revenue tools, and the foundation is now safe. But three truths dominate everything:

1. **It isn't shipped.** 12 commits of value sit on a local branch. Until it deploys, none of it counts and no data is being collected. *Everything else is downstream of this.*
2. **Its data quality is unproven and its estimates are unreliable.** The thing users pay a spy tool for — trustworthy numbers — is heuristic, uncalibrated, and has a known math bug. This, not features, is the product gap.
3. **It cannot see its own data quality.** There is no coverage/freshness/accuracy instrumentation, so quality can't be measured, let alone improved.

Fixing these three is worth more than the other 90 items combined.

---

## Detailed issues (top priority, full analysis)

### ISSUE-1 🟥 Nothing is deployed; no CI/CD, no staging
- **Current implementation:** All recent work is on `audit-fixes` (unpushed). Production runs old `main` with the original critical bugs. No GitHub Actions, no staging, migrations run at app boot.
- **Why it's a problem:** The business gets **zero value** from work that isn't live, and the *running* product still has the auth-bypass and destructive-migration bugs. No CI means regressions ship silently; no staging means the first-ever run of the Alembic migration + country pipeline happens in prod.
- **Recommended solution:** Push the branch → open PR → set up a minimal GitHub Actions pipeline (install, `pytest`, `tsc`, `next build`) → create a Railway staging environment → deploy branch to staging, smoke-test, then merge+deploy to prod while watching the first migration boot.
- **Business impact:** Unblocks *all* value + closes live security holes. **Highest ROI in the repo.**
- **Technical impact:** Establishes the deploy/verify loop everything else depends on.
- **Priority:** 🟥 Critical · **Effort:** M · **ROI:** Extreme.

### ISSUE-2 🟥 Download/revenue estimates are uncalibrated and contain a math bug
- **Current implementation:** `config/rank_curves.py::interpolate_rank_downloads` has dead interpolation variables and a surviving formula that is **non-monotonic with discontinuities at band edges** (a rank-20 estimate can exceed rank-6). `download_estimator`/`revenue_estimator` are pure heuristics with **no ground-truth calibration**.
- **Why it's a problem:** Estimates are the headline "intelligence." When a user cross-checks against a known app and the number is visibly wrong, trust collapses and they churn. This is *the* differentiator vs cheap ASO tools and it's currently weak.
- **Recommended solution:** (a) Fix the interpolation to be monotonic + continuous (anchor each band bound to the next band). (b) Calibrate rank→downloads curves per country×category against *any* obtainable ground truth (App Store Connect samples, known-MAU public apps, or a small purchased set). (c) Show a confidence band and be honest about it.
- **Business impact:** Directly determines whether users trust and pay. Very high.
- **Technical impact:** Localized (2–3 files) for the bug; calibration is a data project.
- **Priority:** 🟥 Critical · **Effort:** M (bug) + L (calibration) · **ROI:** Very high.

### ISSUE-3 🟥 No data coverage / freshness / accuracy instrumentation
- **Current implementation:** `/health` reports job metrics but **nothing** measures distinct apps by source/country, freshness, or accuracy.
- **Why it's a problem:** You cannot improve — or *sell* — data quality you can't measure. Every roadmap decision after shipping is blind without this.
- **Recommended solution:** Add a lightweight metrics endpoint/table: distinct apps by `source` and `country`, apps seen in last 24h/7d, oldest-refresh per tier, ranking rows/day, review coverage per storefront. Spot-check 20 apps vs the live App Store weekly.
- **Business impact:** Turns "we think it's good" into "here's our coverage vs Sensor Tower" — a sales asset.
- **Priority:** 🟥 Critical · **Effort:** S–M · **ROI:** Extreme (enables all quality work).

### ISSUE-4 🟧 Single egress IP is the acquisition throughput ceiling
- **Current implementation:** All Apple traffic goes through one Railway IP with `Connection: close` and a 403 circuit breaker; no proxy support anywhere.
- **Why it's a problem:** Global coverage (175 storefronts × charts × genres + multi-country reviews) needs sustained request volume one IP can't provide without 403s. This caps *how good the data can get* regardless of code.
- **Recommended solution:** Add a rotating **proxy pool** (residential/datacenter) with per-IP rate budgeting + keep-alive (`httpx.Client`/`requests.Session`); make the circuit breaker per-IP. This is the **first real ROI dollar**, not a bigger dyno.
- **Business impact:** Unlocks the coverage/freshness that differentiates the product.
- **Priority:** 🟧 High (after ship+measure) · **Effort:** M · **ROI:** High.

### ISSUE-5 🟧 No retention on rankings/reviews → storage cost bomb + slow queries
- **Current implementation:** `rankings` and `reviews` are append-only; **no unique constraint, no retention job**. Global per-country/genre daily writes would reach ~hundreds of millions of rows/year.
- **Why it's a problem:** On Railway, **storage is the real cost driver** for a global rankings product, and unbounded tables slow every trend/window query. This bites exactly when coverage grows.
- **Recommended solution:** Month-partition `rankings`; write ranking rows **only on change** (+ a daily heartbeat per tier); tiered retention + rollup (T1 daily 90d → weekly; T4 weekly 8w); prune `discovery_queue` done-rows.
- **Business impact:** Keeps infra affordable at scale; protects margins.
- **Priority:** 🟧 High (before widening country collection) · **Effort:** M–L · **ROI:** High.

### ISSUE-6 🟧 Usage-counter race → plan-limit bypass / revenue leak
- **Current implementation:** `plan_enforcement.check_and_increment` does a non-atomic read-modify-write; on failure it `db.rollback()` on the shared request session.
- **Why it's a problem:** Concurrent requests can both pass at the limit boundary (users exceed paid limits), and the rollback can discard the handler's other uncommitted work. Direct revenue leakage + data-integrity risk.
- **Recommended solution:** Atomic `UPDATE workspace_usage SET x = x + 1 WHERE … RETURNING` with the limit enforced in the same statement; use a dedicated short-lived session for accounting.
- **Business impact:** Protects paid-plan revenue.
- **Priority:** 🟧 High · **Effort:** S · **ROI:** High.

### ISSUE-7 🟧 No cascade deletes → orphan data + orphaned live Stripe subscriptions
- **Current implementation:** Legacy `apps` children (`rankings`, `reviews`, `app_versions`, `app_analytics`, `app_keywords`, `opportunities`, `feature_gaps`) have FKs **without `ondelete`**, and App relationships use `lazy="noload"` (cascade won't fire). Deleting a user (admin console) leaves the workspace + its **live Stripe subscription** + usage orphaned.
- **Why it's a problem:** App/user deletion is impossible or leaves paying-Stripe orphans (billing keeps charging); blocks GDPR-style deletion.
- **Recommended solution:** Add `ondelete="CASCADE"` (+ `passive_deletes=True`) to the 8 child FKs via migration; on user delete, cancel the Stripe subscription then delete the sole-owner workspace.
- **Business impact:** Compliance + prevents charging deleted customers.
- **Priority:** 🟧 High · **Effort:** M · **ROI:** High.

### ISSUE-8 🟧 Keywords are not per-country (the deferred half of "global")
- **Current implementation:** Keyword discovery/ranks use a US-centric English keyword list; only charts/rankings/trending/blowing-up/reviews are per-country.
- **Why it's a problem:** ASO managers work per market; US-only keyword intelligence undercuts the "global" promise for a core persona.
- **Recommended solution:** Localized seed sets per storefront language + autocomplete recursion; per-country keyword-rank snapshots; thread `country` through the keyword endpoints/UI (reuse the CountrySelect pattern).
- **Business impact:** Completes the global story for ASO buyers.
- **Priority:** 🟧 High (post-ship) · **Effort:** L–XL · **ROI:** Medium-high.

### ISSUE-9 🟨 Testing is thin, partly broken, and unautomated
- **Current implementation:** 27 test files, but many mock the DB; **5 pre-existing failures** (`test_reviews_intelligence` broken MagicMocks); the country integration suite needs a real Postgres; env is Python 3.9 vs 3.11 target; no CI.
- **Why it's a problem:** Regressions ship silently; the estimate/scoring logic (the product's brain) is under-covered.
- **Recommended solution:** Fix/delete the broken mock tests; add a Postgres service in CI to run integration tests; pin Python 3.11; add coverage for estimators + scoring; run tests + `tsc` + `next build` on every push.
- **Business impact:** Protects the fixes already made; enables safe iteration.
- **Priority:** 🟨 Medium-High · **Effort:** M · **ROI:** Medium-high.

### ISSUE-10 🟨 No error tracking / observability for a data product
- **Current implementation:** stdout logs + `/health`. No Sentry, no metrics, no alerting, no Apple-403 dashboard.
- **Why it's a problem:** In prod you won't know when jobs fail, migrations break, or Apple starts blocking — until users complain.
- **Recommended solution:** Add Sentry (backend + frontend), a minimal metrics exporter, and alerts on job-failure/403-rate/migration-failure.
- **Priority:** 🟨 Medium (before/at launch) · **Effort:** S–M · **ROI:** Medium-high.

---

## What to FIX (condensed)

| Item | Why | Priority | Effort |
|---|---|:--:|:--:|
| Rank-curve interpolation bug (ISSUE-2a) | Wrong estimates | 🟥 | M |
| Usage-counter race (ISSUE-6) | Revenue leak | 🟧 | S |
| Cascade deletes / Stripe orphan (ISSUE-7) | Compliance/billing | 🟧 | M |
| Job `/health` "ok" overcounts failures | Misleading ops | 🟨 | S |
| `app_analytics` dup-row race (no unique on app_id) | Analytics fork | 🟨 | S |
| Naive `datetime.utcnow()` vs timestamptz (remaining sites) | TZ drift | 🟨 | S |
| ILIKE category filter w/o trigram index | Seq scans | 🟨 | S |
| Remaining sync ORM on event loop (some jobs/routes) | Loop stalls | 🟨 | M |
| Duplicate route function names (routes.py) | Shadowing/confusion | 🟩 | S |

## What to ADD

| Item | Why | Priority | Effort |
|---|---|:--:|:--:|
| CI/CD + staging (ISSUE-1) | Ship safely | 🟥 | M |
| Coverage/freshness metrics (ISSUE-3) | See data quality | 🟥 | S–M |
| Proxy pool (ISSUE-4) | Scale acquisition | 🟧 | M |
| Rankings/reviews retention + partitioning (ISSUE-5) | Cost/perf | 🟧 | M–L |
| Sentry + alerting (ISSUE-10) | Ops visibility | 🟨 | S–M |
| Estimate ground-truth calibration (ISSUE-2b) | Trustworthy numbers | 🟥 | L |
| Keywords per country (ISSUE-8) | ASO persona | 🟧 | L–XL |
| App-ID enumeration / sitemap ingestion | Catalog-tail coverage | 🟨 | M |
| Onboarding / empty-state guidance in UI | Activation | 🟨 | M |

## What to REMOVE

| Item | Why | Priority | Effort |
|---|---|:--:|:--:|
| Unused deps: `python-multipart` (prod), `numpy`/`scikit-learn`/`lxml`/`asyncpg` (dev) | Dead weight | 🟩 | S |
| Dead frontend `ideas/IdeasClient.tsx` (route redirects) | Dead code | 🟩 | S |
| Dead scoring paths (`weights.py`, per-app trend v1, `get_top_trending_apps_v2`) | Drift risk | 🟩 | S |
| Playwright path in `AppStoreScraper` (never launched) | Misleading | 🟩 | S |
| Duplicate route/function definitions | Confusion | 🟩 | S |

## What to REWRITE

| Item | Why | Priority | Effort |
|---|---|:--:|:--:|
| Consolidate 4–6 divergent `opportunity_score`/difficulty/volume/CTR formulas into one module | Same metric, different numbers per door | 🟨 | M |
| Single shared `upsert_app_from_itunes` (replace 3 copies) | Inconsistent app records | 🟨 | M |
| `download_estimator` calibration model | Trust | 🟥 | L |
| `apps/[id]/page.tsx` (3.5K lines) → split tabs + lazy-load | Bundle/maintainability | 🟨 | M |

## What to REDESIGN

| Item | Why | Priority | Effort |
|---|---|:--:|:--:|
| Frontend data layer → adopt SWR/react-query | Kills fetch races, adds cache/retry/dedup in one move | 🟨 | M |
| Move scheduler to a **dedicated worker service** (Discovery Engine V2) | Horizontal scaling | 🟨 | L |
| Acquisition → tiered budget lanes + AIMD governor + proxies (V2 design already documented) | Coverage/freshness at scale | 🟨 | XL |
| Rankings storage → partitioned + change-only writes + retention | Cost at scale | 🟧 | M–L |

---

## Unnecessary features (candidates to cut or defer for focus)

The product is **feature-broad but validation-thin**. For a pre-revenue tool, breadth dilutes quality. Consider deferring/hiding until data quality is proven: **ad intelligence, campaign detection, niche radar, app autopsy (LLM cost), app ideas**. Keep the core loop sharp: **charts/rankings → app detail (metadata, estimates, reviews) → trending/opportunities → keywords**. (These are judgment calls, not code defects.)

## UX problems (from code)

| Problem | Priority |
|---|:--:|
| Errors rendered as empty "no data" states on several pages (looks broken vs "error") | 🟨 |
| No global cache → refetch on every navigation; visible flicker | 🟨 |
| Inconsistent number/date formatting across pages | 🟩 |
| `<img>` not `next/image` (screenshots unoptimized) | 🟩 |
| Classification pill counts are page-local but read as filter totals | 🟩 |
| No onboarding / first-run guidance | 🟨 |

## Hidden technical debt

- **Estimates presented as fact** without confidence UI. 🟨
- **In-memory cursors** (keyword daily jobs) reset on every Railway redeploy → coverage skew. 🟨
- **Two chart-fetch paths** (legacy `/us/rss` in `appstore.py` vs per-country in discovery) — the legacy one is being sunset by Apple. 🟨
- **`current_rank` drift** (overwritten by whichever chart scraped last, no chart context). 🟨
- **JSON vs JSONB** drift (models generic JSON; can't GIN-index). 🟩
- **No lint config** in frontend (`next lint` unconfigured). 🟩

---

## CTO verdict

The engineering is in **far better shape than the product is proven**. The temptation — and the pattern so far — is to keep adding features. **Resist it.** The next four moves, in order, are worth more than any new feature: **(1) ship it, (2) measure data quality, (3) fix + calibrate the estimates, (4) add proxies to widen coverage.** Do those and RankSpy becomes a *defensible* product; skip them and it stays an impressive demo. Full sequencing in [12_ROADMAP.md](./12_ROADMAP.md) and [13_NEXT_100_TASKS.md](./13_NEXT_100_TASKS.md).
