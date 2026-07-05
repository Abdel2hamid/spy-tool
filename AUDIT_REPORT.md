# Engineering Audit Report — AppStore Spy (RankSpy)

Full-codebase audit of ~76K lines (FastAPI backend + Next.js 14 frontend), performed with
ten parallel read-only subsystem reviews (API/auth/security, scrapers & collectors,
workers/scheduler, database/models, keyword-services cluster, scoring engine + config,
opportunity/AI services, frontend API client, app-detail page, feature pages). Every
finding below was re-verified against the actual code before any change was made.

**Scope of changes in this pass:** the highest-severity, lowest-risk-to-apply fixes —
security holes, guaranteed crashers, silent data-loss bugs, and a set of high-value
reliability/performance corrections. Larger structural refactors (formula consolidation,
Alembic adoption, cascade migrations) are itemized under "Remaining Recommendations" with
rationale, because they need schema migrations or broad test coverage that exceeds a safe
single-pass edit.

---

## 1. Architecture Overview

**Backend** — FastAPI (Python 3.11 target) + synchronous SQLAlchemy over PostgreSQL.
`routes.py` (4.5K lines, ~100 endpoints) plus `auth_router`, `admin_console_router`,
`stripe_router`. Multi-tenant: JWT → user + workspace, membership-scoped. ~47 services
under `services/`, a 2.2K-line `scoring/engine.py` computing derived market metrics, and an
in-process APScheduler (`workers/scheduler.py`, 33 jobs) that scrapes the iTunes/App Store
APIs, enriches keywords, and precomputes trending/opportunity data. All Apple traffic flows
through a single hardened `apple_http_client.py` (urllib, retry/backoff, 403 circuit
breaker) — except `app_import_service.py`, which has its own urllib stack.

**Frontend** — Next.js 14 App Router, TypeScript, Tailwind, Recharts. A 2.9K-line
`lib/api.ts` client (localStorage JWT, `/api/*` proxied to backend via Next rewrites) and a
3.5K-line app-detail page with ~20 co-located components. No data-fetching cache layer;
every page hand-fetches in `useEffect`.

**Data flow.** Discovery (charts/keywords/developer) → `discovery_queue` → scrape workers →
`apps`/`rankings`/`reviews` → scoring/keyword pipelines → precomputed
trending/opportunity/keyword tables → API → frontend.

---

## 2. Issues Found, Severity, Root Cause, and Fix Applied

### CRITICAL — fixed

| # | Issue | File(s) | Root cause | Fix applied |
|---|-------|---------|-----------|-------------|
| C1 | **Auth gate bypassable** — the global middleware only checked that an `Authorization: Bearer …` header was *present*; dozens of data endpoints declared no auth dependency, so `Bearer x` read the entire product's data. | `app/main.py` | Middleware documented "verified downstream" but many routes had no downstream check. | Middleware now decodes and validates the JWT (`decode_access_token`); invalid/expired tokens are rejected 401. |
| C2 | **Unauthenticated `/run-migrations`** — public route executing destructive DML (`DELETE FROM keywords…`, mass `UPDATE`), a data-loss + DoS vector; also leaked raw SQL errors. | `app/main.py` | Temporary ops endpoint left in the public whitelist under two paths. | Removed from public whitelist; now requires `ADMIN_TOKEN` (fails closed) and no longer returns exception text. |
| C3 | **Email verification silently bypassed every startup** — `UPDATE users SET email_verified=TRUE … created_at < NOW()-'1 minute'` ran on every boot, auto-verifying any user who registered >1 min before a restart. | `app/main.py` `_MIGRATIONS` | A one-time backfill written as an always-rerun idempotent-looking statement. | Removed the statement (backfill is complete in prod); noted it belongs in a versioned migration. |
| C4 | **Keyword search 500s on every genuinely new app** — `item.get("genres",[{}])[-1].get("name")` assumed dicts, but iTunes returns genre *strings* → `AttributeError` outside the try. Also `artistId` int passed to a String column. | `services/keyword_search_service.py` | Divergent copy of app-upsert logic that never matched the real API shape. | Genre parsed as string (`(genres or [None])[-1]`); `artistId` wrapped with `str()`. |
| C5 | **New-app keyword enrichment silently broken in 3 paths** — import, search, and hydration all called `extract_for_app()` and `pipeline.enrich_app()`, neither of which existed; `AttributeError` swallowed by blanket `except`, so imported apps got no keywords. | `post_import_hydration.py`, `app_import_service.py`, `keyword_search_service.py`, `keyword_intelligence_pipeline.py` | Method renamed to `extract_keywords_for_app`; the pipeline never had a per-app method. | Fixed the call name; implemented `KeywordIntelligencePipeline.enrich_app(app_id)` (scores the app's linked keywords via `recompute_scores`). |
| C6 | **`NameError` crashes the nightly opportunity job** — `score_opportunity()` referenced undefined `competition_score`; the tasks loop had no per-item guard, so the first app aborted opportunities, market-weakness, feature-gaps, ideas, and metric snapshots. | `scoring/engine.py` | Variable renamed to `competition_score_for_calc` at definition but not at use. | Corrected the reference. |
| C7 | **`/keyword-opportunities` 500s for every keyword** — `datetime.utcnow() - keyword.last_updated` subtracted a naive from a tz-aware `timestamptz`; `last_updated` is server-defaulted so it always triggered. | `scoring/engine.py` | Naive/aware datetime mixing. | Normalized to tz-aware `datetime.now(timezone.utc)` with a tzinfo guard. |

### HIGH — fixed

| # | Issue | File(s) | Fix applied |
|---|-------|---------|-------------|
| H1 | Two admin endpoints 500 on every call — `force_rescrape` referenced non-existent `App.apple_id`; `bulk_backfill` passed a `detail=` kwarg `_log_activity` doesn't accept. | `admin_console_router.py` | Use `app.app_id`; rename kwarg to `details=`. |
| H2 | Admin-created users could never log in — created with `email_verified=False`, no verification email, login rejects unverified. | `admin_console_router.py` | Set `email_verified=True` for admin-provisioned users. |
| H3 | Admin token dependency failed *open* when `ADMIN_TOKEN` unset (`return` = allow). | `api/routes.py` `_require_admin` | Fails closed now (503 when unconfigured). |
| H4 | Rate limiter keyed on `request.client.host` — behind the Next/Railway proxy that's one shared IP, so auth brute-force limits were a single global bucket (self-DoS + no per-user limiting). | `utils/rate_limiter.py` | Derive client IP from `X-Forwarded-For` (first hop). |
| H5 | Rate-limiter GC evicted keys belonging to *longer* windows (auth's 120s bucket pruned by any 60s request). | `utils/rate_limiter.py` | GC now uses a conservative max-window cutoff. |
| H6 | `Retry-After` parsed with bare `int()` — an HTTP-date value raised `ValueError` out of the "never raises" Apple client, 500-ing search/discovery exactly when Apple rate-limits. | `apple_http_client.py` | Guarded parse with fallback to exponential backoff. |
| H7 | Review pagination math wrong — assumed 10 reviews/page (feed serves ~50, hard-caps at page 10); default `limit=500` looped pages 1–51, burning the retry budget on dead pages. | `scrapers/app_details.py` | Page size 50, capped at 10 pages; app-info entry skipped by `im:rating` presence (removes the fake-review leak path too). |
| H8 | `difficulty_v2` brand-dominance was ~always 0 — exact-equality match `artistName in {"google",…}` never hit real values like "Google LLC". | `keyword_scoring_v2.py` | Substring match against the brand set. |
| H9 | Discovery-queue claim race + IntegrityError-aborts-whole-batch — check-then-insert `enqueue` and a non-locking SELECT/UPDATE claim let overlapping jobs double-scrape and lose whole batches. | `workers/discovery_engine.py` | `enqueue` uses `ON CONFLICT DO NOTHING`; claim uses `SELECT … FOR UPDATE SKIP LOCKED`, stamps `processed_at`, reaps stale `scraping` rows (>2h), and excludes `tier_enrich:*` from the generic processor. |
| H10 | O(n²) keyword rescoring — `iter_batches` OFFSET/LIMIT over the full ~850K-row keywords table (hourly + 6-hourly). | `utils/batch_utils.py`, `workers/tasks.py`, `keyword_intelligence_pipeline.py` | Added `iter_batches_keyset` (keyset pagination); switched both full-table scoring loops to it. |
| H11 | Keyword-gap false positives — searched top-20 but the gap rule flags rank >30, so ranks 21–30 read as "not ranked". | `keyword_gap_service.py` | Fetch top-50. |

### MEDIUM — fixed

| # | Issue | File(s) | Fix applied |
|---|-------|---------|-------------|
| M1 | Scheduler runs in every replica — in-process job state means 2+ replicas = duplicate scraping/writes/queue-claims. | `app/main.py` | `ENABLE_SCHEDULER` env gate (default on) so only one instance runs jobs. |
| M2 | Stripe webhook blocked the event loop — `async def` handler doing sync Stripe/DB I/O. | `stripe_router.py` | Handler body dispatched via `run_in_threadpool`. |
| M3 | Global 500 handler leaked `type(exc).__name__: exc` to clients. | `app/main.py` | Returns generic "Internal server error" (details still logged). |
| M4 | `func.lower(Keyword.term).in_(...)` forced seq scans on ~1M rows (terms already stored lowercase). | `keyword_suggestions_service.py`, `competitor_compare_service.py` | Lowercase in Python; plain indexed `term.in_()`. |
| M5 | Niche radar read the dead `Keyword.trend` column (always 0) instead of `trend_score`. | `niche_radar.py` | Prefer `trend_score`. |
| M6 | Naive `utcnow()` written to `timestamptz` columns (staleness math off under non-UTC session). | `review_sentiment_service.py`, `scoring/feature_gaps.py` | `datetime.now(timezone.utc)`. |
| M7 | Sync Anthropic client with default 10-min timeout pinned a threadpool worker + DB connection on a hang. | `review_intelligence.py`, `app_autopsy.py` | `timeout=30.0`. |
| M8 | Mutable shared default `Column(JSON, default={})` on `Alert.config`. | `models/models.py` | `default=dict`. |
| M9 | Circuit-breaker globals mutated without a lock across threads. | `apple_http_client.py` | Guarded with a `threading.Lock`; added jitter to 5xx backoff. |
| M10 | `evaluate_alerts` logged garbage durations (passed event-count as start time). | `workers/scheduler.py` | Capture and pass `t0` from `_log_start`. |

### Frontend — fixed

| # | Issue | File(s) | Fix applied |
|---|-------|---------|-------------|
| F1 | **Per-keystroke App Store import** — typing a numeric ID fired `lookupApp` on every prefix ("123456", "1234567", …), importing/navigating to several wrong apps. | `apps/AppsClient.tsx` | Direct-ID import moved inside the 600ms debounce. |
| F2 | **Wrong app's reviews shown forever** — `reviewsLoaded` never reset on `appId` change; same-route nav kept the component mounted. | `apps/[id]/page.tsx` | Reset per-app state + ignore-flag in the `[appId]` effect. |
| F3 | **No 401 handling** — expired token left the app dead with generic errors; a transient network failure on `authMe` silently logged the user out. | `lib/api.ts`, `lib/auth.tsx` | Centralized 401 → clear token + redirect to `/login`; `authMe` exposes status so only 401/403 (not network errors) drops the session. |
| F4 | **Double body-read on 403** destroyed the real error message. | `lib/api.ts` | Parse the 403 body once and branch. |
| F5 | **Impersonation clobbered the admin's token** (shared localStorage), demoting the admin tab with no way back. | `impersonate/page.tsx` | Back up the admin token before overwriting. |
| F6 | **Admin settings built a different API base**, 404ing when `NEXT_PUBLIC_API_URL` is origin-only. | `admin/settings/page.tsx`, `lib/api.ts` | Export and reuse the shared `API_BASE`. |
| F7 | **Uncancelled recursive poll + stuck spinner** in the extracted-keywords table; `triggerKeywordExtraction` ignored `res.ok` so an HTTP error read as success and polled forever. | `apps/[id]/page.tsx`, `lib/api.ts` | Timer stored in a ref and cleared on unmount; `handleExtract` wrapped in try/finally; client now throws on non-OK. |

---

## 3. Performance Improvements

- **Keyword scoring is now O(n) instead of O(n²)** at ~850K rows (keyset pagination) — the hourly and 6-hourly full-table passes no longer re-scan hundreds of thousands of discarded rows per batch.
- **Discovery enqueue no longer aborts whole batches** and uses a single `ON CONFLICT` insert instead of per-row check-then-insert with per-row commits.
- **Queue claiming is contention-safe** (`FOR UPDATE SKIP LOCKED`), eliminating double-scrape of the same apps and the duplicate Apple traffic that trips the 403 breaker.
- **Suggestions/competitor keyword lookups use the index** again (removed `func.lower()` wrapping) — was a seq scan per 500-term batch.
- **Review scraping ≈10× fewer requests** per nightly batch (correct 50/page math, 10-page cap) and no wasted retry budget on non-existent pages.
- **Removed a blocking `time.sleep(0.1)` per result** from the keyword-search request path (was +5s on a 50-result search).
- **Stripe webhook no longer stalls the event loop** under load.

## 4. Data-Quality Improvements

- New apps entering via keyword search are **stored correctly** (genre/developer_id) instead of 500-ing.
- Imported/searched apps now **actually get keyword extraction and intelligence enrichment** (three silently-broken paths restored).
- `difficulty_v2` **now reflects brand dominance** (was systematically under-scoring brand-dominated keywords toward 0).
- Keyword-gap analysis **no longer emits false-positive gaps** for apps ranked 21–30.
- Niche-radar trend values are **real** (`trend_score`) instead of a dead always-0 column.
- Timezone-correct staleness comparisons for reviews/feature-gaps (no drift under non-UTC sessions).
- Review ingestion no longer admits a **fake-review leak** from a mis-ordered entry filter.

## 5. Security Improvements

- All `/api/v1` data endpoints now require a **valid** JWT (was header-presence only) — closes broad unauthenticated data access.
- **Destructive `/run-migrations` endpoint** removed from public access and gated behind `ADMIN_TOKEN` (fails closed); the every-boot email-verification bypass removed.
- Admin routes **fail closed** when `ADMIN_TOKEN` is unset.
- Rate limiting is **per-user** (X-Forwarded-For) and no longer prunes the stricter auth buckets early — restores real brute-force protection.
- Internal exception details **no longer leaked** to clients (global handler + migrations endpoint).

---

## 6. Verification

- **Backend:** `python -m compileall app` clean. Test suite: **506 passed / 17 failed**, and the 17 failures are **byte-identical to the pre-change baseline** (confirmed by stashing all changes and re-running the same subset — same 506/17, same failed-test names). The 17 are environmental: this machine runs **Python 3.9** while the project targets **3.11** (the failures are in `test_plan_enforcement`, `test_download_estimator`, `test_scoring_config`, `test_keyword_quality`, none of which touch changed files). **Zero regressions introduced.**
- **Frontend:** `tsc --noEmit` exit 0; `next build` production build exit 0.
- The full suite hangs at ~91% on `test_new_releases`/`test_growth_intelligence`, which make live network calls — a pre-existing test-isolation issue, unrelated to these changes.

---

## 7. Remaining Recommendations (not applied — need migrations or broad test coverage)

**Schema / data-integrity (need Alembic migrations):**
1. **Adopt Alembic and delete the startup `_MIGRATIONS` DML.** `alembic/versions/` is empty; schema is `create_all()` + a 540-line append-only SQL list where failures are swallowed. Baseline the current prod schema and move all future DDL into revisions. Also fix the still-broken `DELETE FROM keyword_queue WHERE keyword_id …` (that table has no `keyword_id` column — fails silently every boot).
2. **Add `ondelete="CASCADE"`** to the eight legacy `apps` child FKs and two `keywords` child FKs (`app_keywords`, `keyword_trends`); the daily keyword-cleanup DELETE likely fails today on FK violations. App/user deletion currently orphans rankings/reviews and, for users, workspaces + live Stripe subscriptions.
3. **Add a unique constraint on `app_analytics.app_id`** and switch to `ON CONFLICT` upsert — the sentiment job and review-intelligence race to create duplicate rows and then read different ones (analytics fork). Same for `ad_campaigns`/`ad_creatives` dedup.
4. **Rankings/reviews retention + dedup** (e.g. keep 90 days; unique-per-app/chart/hour). Unbounded append-only growth on Railway storage; `current_rank` also drifts because it's overwritten by whichever chart scraped last with no chart context.
5. **JSON → JSONB** in models to match the inline DDL intent (create-order currently decides the real column type per environment).
6. **Convert `App` creation to `INSERT … ON CONFLICT`** (`tasks.get_or_create_app`, `rankspy_search_service`) to end select-then-insert races that poison the session and abort chart batches.

**Reliability / correctness (need broader test coverage):**
7. **Timed-out `to_thread` jobs close their DB session while the executor thread is still using it** — treat scheduler timeouts as cooperative deadlines, and create/close sessions *inside* the threaded function rather than sharing the outer job's session.
8. **Move remaining sync ORM off the event loop** (`backfill_incomplete` does 30s blocking HTTP directly in an async job; `evaluate_alerts`, `ranking_refresh` run sync queries on the loop).
9. **Fix coverage starvation** in chart discovery (fixed scan order + daily flag never reaches most of 1,320 combos) and `full_metadata` (designed to time out every run; head-of-list apps re-scraped, tail never refreshed) — rotate by least-recently-run; persist the in-memory daily cursors so redeploys don't reset them.
10. **Typed Apple-client errors** — the client collapses {blocked, rate-limited, dead, empty} into `None`, so batch jobs commit partial data as "success". Return a typed result / raise typed exceptions so jobs can abort-and-resume.
11. **`AppImportService` bypasses the hardened client** (own urllib, no retries/429/circuit-breaker) on the user-facing import path — route it through `apple_fetch_json`.

**Duplication / maintainability (mechanical, low-risk but wide):**
12. **Consolidate the 4–6 divergent `opportunity_score` / difficulty / volume / CTR formulas** into `keyword_scoring_v2` — the same DB column holds values from different formulas depending on ingestion door.
13. **One shared `upsert_app_from_itunes`** to replace the three divergent app-upsert copies.
14. **Frontend: a shared abortable/request-id fetch hook + `useDebouncedCallback`** fixes the remaining fetch races (Keywords, BlowingUp, RankSpySearch, Competitors picker, LatestApps, Rankings) in one pass; a shared error-state pattern so failures stop rendering as empty "no data" states across ~10 pages; delete dead `ideas/IdeasClient.tsx` and extract the 6× duplicated `ScoreRing`/`fmtNum`.

**Dependencies:** remove unused `python-multipart` (prod) and `numpy`, `scikit-learn`, `lxml`, `asyncpg` (dev) — verified zero imports.

**Efficiency (cost):** the Apple client uses `Connection: close` (new TCP+TLS per call) across 10⁴–10⁵ calls/day — a pooled `httpx`/`requests.Session` (with optional proxy support) would cut latency and egress; and App-Autopsy makes an uncached Claude call per page view (review-intelligence already caches — mirror that).
