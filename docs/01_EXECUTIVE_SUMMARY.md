# 01 — Executive Summary, Product Vision & Production Readiness

> Part of the **RankSpy Master Technical Documentation (Project Bible)**. See [INDEX.md](./INDEX.md).
> Status legend: ✅ Implemented · 🟡 Partially Implemented · 🔴 Planned / Not built.
> Everything below is derived from the actual code on the `audit-fixes` branch (12 commits ahead of `origin/main`).

---

## 1. Executive Summary

**RankSpy** (codebase: `appstore-spy`) is an **App Store market-intelligence SaaS** — a "spy tool" for iOS apps — intended to compete with Sensor Tower, AppMagic, and App Radar. It monitors the Apple App Store and surfaces competitive insight: top charts, rankings, trending/"blowing-up" apps, keyword intelligence/ASO, reviews & sentiment, download/revenue estimates, competitor comparison, and auto-generated app ideas — behind a multi-tenant, plan-gated (Stripe) SaaS.

### What it actually is today (by the numbers, from code)

| Dimension | Count | Notes |
|---|---:|---|
| Backend | FastAPI + PostgreSQL (sync SQLAlchemy 2.0 + psycopg2) | Python 3.11 target |
| Database tables | **43** | Managed by Alembic (5 revisions) ✅ |
| HTTP endpoints | **~156** | routes.py 111 + admin 33 + auth 8 + stripe 4 |
| Services | **49** | `backend/app/services/` |
| Scrapers/collectors | **4** + shared HTTP client | iTunes RSS / lookup / search / autocomplete |
| Scheduled jobs | **34** | in-process APScheduler, single-instance |
| Frontend | Next.js 14 (App Router, TS, Tailwind, Recharts) | **33** route dirs, **21** components |
| API client | `frontend/src/lib/api.ts` | ~3,045 lines, ~90 exported functions |
| Backend tests | **27** files | mostly unit (mocked DB) + 1 country-aware integration suite |
| AI usage | **2** services call Anthropic (Haiku 4.5) | review intelligence + app autopsy |

### The single most important fact

🔴 **None of the recent work is live.** All 12 commits — the security fixes, Alembic adoption, scheduler hardening, and the entire multi-country feature set (charts, rankings, genres, trending, blowing-up, reviews per storefront) — sit on the local `audit-fixes` branch. They have **never been pushed to GitHub and never deployed**. The *running* product is still the old `main`, which contains the original critical bugs. **There is therefore zero real multi-country data collected yet** — the pipeline exists in code but has not run in production.

### Honest one-paragraph status

The codebase has a **broad, credible feature surface** and, after the recent audit + hardening, a **materially safer foundation** (versioned migrations, validated auth, thread-safe scheduler). The last stretch turned it from a US-only tool into a **code-complete multi-storefront intelligence product**. However, it is **pre-deployment, pre-revenue, and its data quality is unproven** — the "intelligence" (download/revenue estimates) is heuristic and uncalibrated with a known math bug, coverage is chart/keyword-seeded (no catalog enumeration), and everything is gated by a **single egress IP**. The gap to "a spy tool users love" is **not more features — it is shipping, measuring real data quality, and making the estimates trustworthy.**

---

## 2. Product Vision

### Mission
Give indie developers, ASO managers, and product teams **trustworthy, fresh, global App Store intelligence** at a fraction of Sensor Tower's price — so a small team can answer "who's winning, where, and why" for any app in any storefront.

### Target users (inferred from feature set — not from any written spec)
- **Indie / small-studio developers** — the scoring engine explicitly excludes big-brand apps to surface competable opportunities. ✅ (bias baked into `_is_big_brand_app`, opportunity scoring)
- **ASO managers** — keyword intelligence, difficulty/volume, opportunity scoring. ✅ (breadth) / 🟡 (accuracy unvalidated)
- **Product/market researchers** — trending, blowing-up, niche radar, competitor compare, ideas. ✅ surface / 🟡 depth

### Differentiators the code aims at
| Differentiator | State |
|---|---|
| Global (all-storefront) coverage | 🟡 code-complete for charts/rankings/genre/trending/blowing-up/reviews; **not yet run at scale**; long-tail catalog uncovered |
| Per-market reviews & sentiment | 🟡 collection + API + UI built; bounded on a single IP; sentiment is heuristic |
| Download / revenue estimates | 🟡 heuristic, uncalibrated, known interpolation bug |
| Auto-generated app ideas / opportunities | ✅ rule-based (not LLM) |
| Indie-friendly (big brands filtered) | ✅ |
| Low price point | 🔴 (business, not code) |

### Explicit non-goals (today)
- Android / Google Play (iOS App Store only).
- Keywords **per country** (localized keyword ranks) — 🔴 deferred; only reviews/charts/rankings/trending are per-country.
- Ad intelligence at scale — 🟡 heuristic Apple Search Ads + optional Meta Ads Library.

---

## 3. Production Readiness Assessment (score every area 0–100)

Scores reflect the **current `audit-fixes` code**, judged for a **paid SaaS**. "Readiness" blends correctness, completeness, and operability. A score is *not* a grade of effort — it's distance-to-production.

| # | Area | Score | Rationale (from code) |
|---|------|:---:|---|
| 1 | **Security** | **72** | Auth now JWT-validated in middleware; tenant isolation via membership join; admin fails closed; Stripe webhook verified. Open: usage-counter race, token in localStorage, replayable email-verify token, no cascade deletes (orphan data incl. live Stripe subs). |
| 2 | **Correctness** | **74** | Critical crashers/silent-data-loss fixed; country isolation tested. Held down by unvalidated estimates + a known rank-curve interpolation bug + pre-existing broken tests. |
| 3 | **Reliability** | **70** | Scheduler thread-safe + single-instance gate; circuit breaker; retries. Held down by remaining sync-ORM-on-loop jobs, no queue/rankings retention, in-memory cursors reset on redeploy. |
| 4 | **Data Quality** | **48** | Per-country plumbing exists but **unrun**; estimates uncalibrated; no catalog enumeration; metadata gaps (IAP, version history fragile); no retention. This is the make-or-break gap. |
| 5 | **Data Coverage** | **40** | Charts + keywords only; ~5–8% of full catalog reachable; multi-country code-complete but not yet collecting. |
| 6 | **Performance** | **74** | Keyset pagination, batch prefetch, index-usable lookups. Bottlenecks: N+1 admin/list endpoints, ILIKE category filters w/o trigram index, per-item session churn. |
| 7 | **Scalability** | **55** | Single-instance scheduler, single egress IP (real ceiling), unbounded rankings/reviews growth, shared DB pool. Clear path (proxies, worker split, retention) but not built. |
| 8 | **Maintainability** | **62** | Alembic adopted; changes surgical + commented. Dragged by duplicated logic (scoring formulas, donut components), dead code, no lint config, 3.5K-line files. |
| 9 | **API design** | **70** | Consistent `/api/v1`, workspace-scoped, country params added. Duplicate route names, some unbounded queries, inconsistent error bodies. |
| 10 | **Frontend/UX** | **60** | Broad feature surface, shared CountrySelect, race-guards on key pages. No SWR/cache, errors-as-empty-states elsewhere, huge un-split app-detail, `<img>` not next/image. |
| 11 | **Testing/QA** | **45** | 27 files but many mock-only; 5 pre-existing failing (broken mocks); no CI; integration tests need a DB. Env is Python 3.9 vs 3.11 target. |
| 12 | **Deployment/DevOps** | **42** | Railway + Nixpacks; migrations run at startup (now Alembic). **Not deployed**; no CI/CD, no staging, no secrets rotation, single instance. |
| 13 | **Monitoring/Observability** | **38** | `/health` with pool + job metrics; structured logs. No error tracking (Sentry), no metrics/dashboards, no alerting. |
| 14 | **AI systems** | **65** | 2 services on Haiku 4.5 with 30s timeout; autopsy uncached (cost). Most "AI" is actually rule-based (honest but worth clarifying to buyers). |
| 15 | **Billing/Monetization** | **68** | Stripe checkout + webhooks + plan enforcement present; usage-counter race + no idempotency keys. |

### Composite readiness

| Rollup | Score |
|---|:---:|
| **Engineering foundation** (security/correctness/reliability/perf/maintainability) | **~70 / 100** |
| **Product value** (data quality + coverage — what users pay for) | **~44 / 100** |
| **Operational readiness** (deploy/monitor/test) | **~42 / 100** |
| **Overall production readiness** | **~55 / 100** |

**Verdict (CTO one-liner):** *Structurally sound and feature-broad, but not production-proven. The bottleneck to a lovable product is no longer features — it is shipping, measuring, and calibrating data quality.* Full brutal review in [04_CTO_REVIEW.md](./04_CTO_REVIEW.md).
