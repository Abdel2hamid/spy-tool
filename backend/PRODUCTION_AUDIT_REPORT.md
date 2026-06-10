# AppStore Spy - Complete Production Audit Report

**Date:** 2026-06-10
**Scope:** Full-stack audit of all 16 features, 30 models, 28 scheduler jobs, 100+ endpoints, 40+ services
**Platform:** FastAPI + PostgreSQL + Next.js 14 on Railway

---

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| Total findings | 97 |
| P0 (Critical) | 8 |
| P1 (High) | 19 |
| P2 (Medium) | 38 |
| P3 (Low/Cleanup) | 32 |
| Features Healthy | 5 |
| Features Partial | 8 |
| Features Broken | 3 |

**Production Readiness Score: 52/100**

The platform has a strong foundation with good frontend error handling and comprehensive scraping infrastructure. However, critical issues in plan enforcement, fabricated metrics, scaling bottlenecks, and data integrity gaps prevent it from being production-grade for paying customers.

---

## PART 1: FEATURE-BY-FEATURE STATUS

### 1. DASHBOARD
**STATUS: PARTIAL** | Severity: P1

| Aspect | Detail |
|--------|--------|
| Data sources | `/dashboard/stats` (6 COUNT queries), `/trending?limit=5`, `/opportunity-of-day`, `/dashboard/keyword-highlights` |
| Required tables | `apps`, `keywords`, `app_trending_scores`, `rankings`, `opportunities` |
| Required jobs | `trending_compute`, `opportunity_compute`, `hourly_scoring` |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F1 | P1 | **Trending count shows max 5.** Frontend uses `trendingApps.length` (capped at fetch limit=5) instead of `stats.trending_apps_count`. Dashboard card never shows more than "5" even with 500 trending apps. |
| F2 | P1 | **Dashboard cache is per-process.** `_DASHBOARD_CACHE` is a Python dict. With multiple Uvicorn workers, each maintains a separate cache, multiplying DB hits by worker count. |
| F3 | P2 | **Stats endpoint has no error handling.** Any DB failure returns raw 500 to the user. |
| F4 | P2 | **Silent error swallowing on frontend.** All 4 data fetches use `.catch(console.error)` leaving UI at zeros with no error indicator. |

---

### 2. APPS (List + Detail)
**STATUS: PARTIAL** | Severity: P1

| Aspect | Detail |
|--------|--------|
| Data sources | iTunes Lookup API, iTunes Search API, iTunes RSS reviews |
| Required tables | `apps`, `categories`, `opportunities`, `app_market_weakness`, `feature_gaps`, `reviews`, `app_versions`, `app_analytics` |
| Required jobs | `hourly_reviews_ratings`, `full_metadata`, `queue_processor`, `sentiment_analysis` |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F5 | P0 | **Missing auth on POST/PATCH `/apps`.** Anyone can create or modify app records without authentication. |
| F6 | P1 | **Fabricated analytics object.** `GET /apps/{id}/analytics` returns an all-zeros object with `id=0` and `computed_at=now()` when no data exists. Frontend shows this as if it's real computed data. |
| F7 | P1 | **`has_in_app_purchases` filter is broken.** Compares a JSON/text column to a boolean. Filter never matches correctly. |
| F8 | P2 | **Search uses full table scan.** `ILIKE '%term%'` on `description` (TEXT column) with no index. Extremely slow on 55K+ apps. |
| F9 | P2 | **GET with write side effects.** `/apps/{id}/install-estimate`, `/apps/{id}/market-weakness`, `/apps/{id}/feature-gaps` all compute and persist data on GET requests, violating REST semantics. |
| F10 | P2 | **Double query execution.** `query.count()` + `query.offset().limit()` means every list request runs the full query twice. |

---

### 3. KEYWORDS
**STATUS: PARTIAL** | Severity: P1

| Aspect | Detail |
|--------|--------|
| Data sources | iTunes Search API, Apple autocomplete, Google Trends |
| Required tables | `keywords`, `keyword_metrics`, `app_keywords`, `keyword_search_snapshots`, `keyword_trends` |
| Required jobs | `keyword_intelligence`, `keyword_scoring`, `keyword_discovery`, `keyword_rank_tracker` |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F11 | P0 | **Fabricated search_volume.** `update_keyword_metrics()` sets `search_volume = app_count * 850`. A keyword with 3 associated apps shows search_volume=2,550. This is entirely fabricated and displayed as real data. |
| F12 | P0 | **Fabricated difficulty.** `difficulty = min(app_count, 60)`. A keyword with 10 competing apps shows difficulty=10. No real keyword difficulty measurement. |
| F13 | P1 | **Fabricated trend values.** Keyword `trend` is set from a static category map (e.g., "ai"=8.5, "gpt"=8.0, default=3.0). Never changes, never reflects real trends. |
| F14 | P1 | **`ads_presence` always 0.** `GET /keywords/enhanced` hardcodes `ads_presence=0.0` and `feature_gap_count=0` for every keyword. |
| F15 | P1 | **Classification filter returns wrong total.** When `classification` is active, `total_count` is the unfiltered SQL count while results are filtered in Python. Pagination metadata is incorrect. |
| F16 | P2 | **Classification loads 5000 rows into memory.** `q.limit(5000)` then filters in Python instead of SQL. |
| F17 | P2 | **Trend endpoint aggregates in Python.** `GET /keywords/{term}/trend` loads all snapshots into memory then groups by day. Should use SQL GROUP BY. |

---

### 4. RANKINGS
**STATUS: PARTIAL** | Severity: P1

| Aspect | Detail |
|--------|--------|
| Data sources | iTunes RSS feeds (top charts) |
| Required tables | `rankings`, `categories` |
| Required jobs | `full_metadata` (scrape_top_charts), `bootstrap_data` |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F18 | P1 | **Rankings depend entirely on Apple RSS feeds.** If Apple returns 403 (common), `rankings` table stays empty. Bootstrap job mitigates this for existing apps but does not create new ranking data going forward. |
| F19 | P2 | **No pagination on rank history.** `.all()` loads all ranking rows for the date range into memory. High-frequency snapshots over 90 days = thousands of rows. |
| F20 | P2 | **Chart discovery too slow.** `discovery_charts` batch_size=12 with 1,320 combinations = 9 days to complete a full cycle. Should be ~60 per batch. |

---

### 5. TRENDING
**STATUS: HEALTHY** | Severity: None

| Aspect | Detail |
|--------|--------|
| Data sources | Precomputed `app_trending_scores` table |
| Required tables | `app_trending_scores`, `apps`, `rankings` |
| Required jobs | `trending_compute` (every 10 min) |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F21 | P2 | **`/trending/v2` is 100% duplicate of `/trending`.** Identical function body, only log messages differ. Pure dead code. |
| F22 | P3 | **Legacy `get_top_trending_apps` (v1) still exists.** Has N+1 pattern (~5 queries per app). The v2 batch-prefetch method is correct. |

---

### 6. BLOWING UP
**STATUS: HEALTHY** | Severity: None

| Aspect | Detail |
|--------|--------|
| Data sources | Precomputed `app_blowing_up_scores` table |
| Required tables | `app_blowing_up_scores`, `apps`, `rankings` |
| Required jobs | `blowing_up_compute` (every 15 min) |

No significant issues. Well-designed precomputation with proper batch prefetch.

---

### 7. OPPORTUNITIES
**STATUS: PARTIAL** | Severity: P1

| Aspect | Detail |
|--------|--------|
| Data sources | `daily_opportunities`, `weekly_opportunities`, keyword scores, scoring engine |
| Required tables | `daily_opportunities`, `weekly_opportunities`, `keywords`, `apps`, `app_trending_scores` |
| Required jobs | `opportunity_compute`, `weekly_opportunities_compute`, `hourly_scoring` |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F23 | P1 | **`min_probability=0.0` filter is broken.** `GET /opportunities` uses `if min_probability:` which is falsy for 0.0. Passing `min_probability=0.0` does not filter. |
| F24 | P1 | **Opportunity scores based on fabricated metrics.** Since keyword search_volume and difficulty are fabricated (F11, F12), any opportunity score derived from them is unreliable. |
| F25 | P2 | **Two systems write `daily_reports`.** `opportunity_compute` and `hourly_scoring` both write to `daily_reports.opportunity_of_day`. They can overwrite each other. |

---

### 8. CAMPAIGNS
**STATUS: HEALTHY** | Severity: None

| Aspect | Detail |
|--------|--------|
| Data sources | Rankings, reviews, metric snapshots, ad data |
| Required tables | `growth_events`, `apps`, `app_blowing_up_scores` |
| Required jobs | `campaign_detection` (every 2h) |

Well-structured with batch prefetch. No significant issues.

---

### 9. AD INTELLIGENCE
**STATUS: HEALTHY** | Severity: None

| Aspect | Detail |
|--------|--------|
| Data sources | Apple Search Ads heuristics, Meta Ads Library |
| Required tables | `ad_campaigns`, `ad_creatives`, `apps` |
| Required jobs | `ad_intelligence` (every 6h) |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F26 | P2 | **`is_sponsored` always False in search snapshots.** iTunes API has no ad data. All results labeled organic. |

---

### 10. COMPETITORS
**STATUS: BROKEN** | Severity: P1

**The page is a "Coming Soon" placeholder with no backend integration.** No API endpoints, no data, no logic.

---

### 11. FEATURE GAPS
**STATUS: PARTIAL** | Severity: P2

| Aspect | Detail |
|--------|--------|
| Data sources | Reviews (NLP extraction of feature requests) |
| Required tables | `feature_gaps`, `reviews`, `apps` |
| Required jobs | `feature_gap` (every 2h), also `hourly_scoring` (redundant) |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F27 | P2 | **Redundant computation.** Both `feature_gap` job and `hourly_scoring` job compute feature gaps. Double work, potential data overwrite. |
| F28 | P2 | **No auth on analysis trigger.** `POST /apps/{id}/feature-gaps/analyze` has no authentication. Anyone can trigger expensive analysis. |

---

### 12. MARKET WEAKNESS
**STATUS: PARTIAL** | Severity: P2

| Aspect | Detail |
|--------|--------|
| Data sources | Reviews per country, negative review ratios |
| Required tables | `app_market_weakness`, `reviews`, `apps` |
| Required jobs | `hourly_scoring` |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F29 | P2 | **N+1 upsert pattern.** Per-country query for existing row, then update or insert. Should use `ON CONFLICT DO UPDATE`. |

---

### 13. APP AUTOPSY
**STATUS: PARTIAL** | Severity: P1

| Aspect | Detail |
|--------|--------|
| Data sources | App metadata + LLM analysis (Claude API) |
| Required tables | `apps`, `reviews`, multiple scoring tables |
| Required jobs | None (on-demand) |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F30 | P1 | **Synchronous LLM call by default.** `GET /apps/{id}/autopsy?use_llm=true` (default) blocks a worker thread for 10-30 seconds. No rate limiting, no plan enforcement. |
| F31 | P1 | **No caching.** Every GET request triggers a fresh LLM call. |

---

### 14. ANALYTICS
**STATUS: PARTIAL** | Severity: P2

| Aspect | Detail |
|--------|--------|
| Data sources | Reviews (sentiment analysis, theme extraction) |
| Required tables | `app_analytics`, `reviews` |
| Required jobs | `sentiment_analysis` (hourly) |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F32 | P2 | **AppAnalytics rows accumulate unbounded.** Each recompute appends a new row. No pruning visible. |
| F33 | P2 | **Fabricated analytics fallback.** (See F6) |

---

### 15. REVIEWS
**STATUS: HEALTHY** | Severity: None

| Aspect | Detail |
|--------|--------|
| Data sources | iTunes RSS Customer Reviews |
| Required tables | `reviews`, `apps` |
| Required jobs | `hourly_reviews_ratings`, `review_scraper`, `sentiment_analysis` |

Well-structured with proper pagination and sentiment analysis pipeline.

---

### 16. VERSIONS
**STATUS: PARTIAL** | Severity: P2

| Aspect | Detail |
|--------|--------|
| Data sources | App Store HTML scraping + iTunes API fallback |
| Required tables | `app_versions`, `apps` |
| Required jobs | `full_metadata` |

**Issues:**
| # | Sev | Finding |
|---|-----|---------|
| F34 | P2 | **HTML scraping is fragile.** Depends on Apple's undocumented page structure. CSS selectors like `"version-history__item"` break on redesigns. |
| F35 | P3 | **`is_latest` flag needs manual maintenance.** When a new version is inserted, old "latest" must be unset. Not always handled atomically. |

---

## PART 2: CROSS-CUTTING FINDINGS

### SECURITY & AUTH

| # | Sev | Finding | Impact |
|---|-----|---------|--------|
| S1 | P0 | **`_NoOpEnforcer` gives unauthenticated users unlimited access.** When `PlanEnforcer.from_token()` gets no/invalid credentials, it returns a no-op enforcer. Unauthenticated users get more access than Pro plan users. | All enforced endpoints bypassed |
| S2 | P0 | **`access_premium` is defined but never enforced.** `can_access_premium()` is never called anywhere. Free-plan users access all premium features. | Plan gating is fiction |
| S3 | P0 | **Unknown plan codes silently upgrade to "pro".** `get_effective_plan()` falls back to `"pro"` for unrecognized plan codes. A typo in plan_code grants unlimited access. | Billing bypass |
| S4 | P1 | **13 mutating endpoints lack authentication.** POST `/apps`, PATCH `/apps/{id}`, POST `/apps/{id}/feature-gaps/analyze`, POST `/keywords/pipeline/run`, POST `/keywords/discovery/run`, POST `/keyword-tracker/search`, POST `/apps/{id}/metrics/compute`, POST `/apps/{id}/ads/scan`, POST `/apps/{id}/growth-events/detect`, and more. | Data corruption by anonymous users |
| S5 | P1 | **JWT secret auto-generates on restart.** If `JWT_SECRET` env var is not set, all tokens are invalidated on every Railway deploy. Users are silently logged out. | Auth regression |
| S6 | P2 | **No trial expiration enforcement.** `get_effective_plan()` never checks `trial_ends_at`. Expired trials retain trial access indefinitely if the status-flipping job fails. | Revenue leakage |
| S7 | P2 | **No password change rate limiting.** `POST /auth/password` has no rate limit. Allows brute-force of current password. | Account security |
| S8 | P2 | **Admin token defaults to empty string.** If `ADMIN_TOKEN` is not set, admin endpoints may be unprotected. | Admin access bypass |

---

### DATA INTEGRITY

| # | Sev | Finding | Impact |
|---|-----|---------|--------|
| D1 | P0 | **Fabricated search_volume (F11).** `search_volume = app_count * 850` displayed as real data. | Users make business decisions on fake numbers |
| D2 | P0 | **Fabricated difficulty (F12).** `difficulty = min(app_count, 60)` displayed as real metric. | Misleading keyword competition data |
| D3 | P1 | **Fabricated trend values (F13).** Static category map, never changes. "ai"=8.5 forever. | Stale/fake trend data |
| D4 | P1 | **Two different `trend_score` formulas.** `score_opportunity` uses trajectory-based formula. `_build_scored_opportunities` uses position-based formula. Both output field named `trend_score`. | Inconsistent scoring |
| D5 | P1 | **Hardcoded sidebar identity.** Shows "Admin" / "admin@appstore.ai" for ALL users regardless of actual identity. | Confusing for all non-admin users |
| D6 | P2 | **`rank_velocity` penalizes more data points.** `(first_rank - last_rank) / len(ranks)` divides by data point count instead of time span. More frequent snapshots = lower velocity score. | Scoring inconsistency |
| D7 | P2 | **`calculate_category_growth` measures activity not growth.** Counts distinct apps with any ranking, multiplied by 5. A stable category with 20 ranked apps gets growth=100. | Misleading metric |
| D8 | P2 | **No rating validation (1-5 range).** Reviews with rating=0, -1, or 99 silently corrupt sentiment scoring and analytics. | Score corruption |
| D9 | P2 | **Redundant columns: `primary_category` (string) vs `category_id` (FK).** Same data stored two ways. Can go out of sync. | Data inconsistency |
| D10 | P2 | **Legacy columns never removed.** `Keyword.search_volume/difficulty/trend/last_updated` duplicate `KeywordMetrics`. `AppKeyword.position` duplicates `AppKeyword.rank`. | Schema bloat |

---

### SCHEDULER & JOBS

| # | Sev | Finding | Impact |
|---|-----|---------|--------|
| J1 | P1 | **No persistent job store.** `MemoryJobStore` means all jobs fire simultaneously on restart. Railway restarts = thundering herd of Apple API requests. | Rate limiting / 403 cascade |
| J2 | P1 | **`hourly_reviews_ratings` cannot scale.** Attempts to refresh ALL apps every hour. At 55K apps with 15 concurrency and 60s timeout per app, needs ~61 hours. 1h timeout truncates at ~54 apps. | Most apps never refreshed |
| J3 | P1 | **`full_metadata` cannot scale.** Sequential scrape of ALL apps. At 3 HTTP calls/app + 0.5s delays, 55K apps = ~23 hours. 2h timeout truncates at ~4,800 apps. | Most apps stale |
| J4 | P1 | **`discovery_queue` "scraping" status leak.** If timeout kills a job while items are "scraping", they are permanently stuck. No recovery job exists. | Items lost from processing |
| J5 | P1 | **`hourly_scoring` is a mega-job.** Does keyword pruning, scoring, feature gaps, market weakness, idea generation, metric snapshots, AND daily reports all in one pass. Duplicates work of 4+ other jobs. | Redundant computation, race conditions |
| J6 | P2 | **`keyword_queue` is a dead queue.** Items are written but nothing reads or processes them. Table grows unbounded. | Wasted storage, misleading architecture |
| J7 | P2 | **`discovery_queue` never cleaned.** Done/failed items accumulate forever. Slows down dedup queries. | Degrading performance |
| J8 | P2 | **Three keyword pruning mechanisms.** `hourly_scoring` inline, `keyword_cleanup_daily`, `keyword_quality_pruning` all delete keywords using different rules. Can conflict with discovery jobs. | Race conditions, data loss |
| J9 | P2 | **`keyword_discovery_daily` and `keyword_discovery_phase1_daily` cannot scale.** Both process ALL apps (55K). With batches of 10 and 2-3s pauses, runtime exceeds the 2h timeout. | Most apps never processed |
| J10 | P2 | **Stale year modifier.** `MASS_KEYWORDS` uses `"2024"` suffix. It's now 2026. Search terms like "productivity 2024" are outdated. | Reduced discovery effectiveness |
| J11 | P2 | **`blowing_up_compute` runs every 15 min.** Rankings only update hourly at most. 15-min interval is wasteful -- 4x the necessary computation. | Wasted CPU |
| J12 | P3 | **`bootstrap_data` has no timeout decorator.** Unlike every other job, it has no `_with_timeout` wrapper. | Could run indefinitely |

---

### DATABASE HEALTH

| # | Sev | Finding | Impact |
|---|-----|---------|--------|
| DB1 | P1 | **~19 redundant indexes.** Many single-column indexes are prefixes of existing composite indexes. Extra write overhead on every INSERT/UPDATE. | 10-15% write penalty, wasted storage |
| DB2 | P1 | **11 FKs missing `ondelete="CASCADE"`.** Raw SQL DELETEs on `apps` will fail for `rankings`, `reviews`, `app_versions`, `app_analytics`, `app_keywords`, `opportunities`, `app_market_weakness`, `feature_gaps`, `keyword_trends`. | Cannot delete apps via SQL |
| DB3 | P2 | **`keyword_search_snapshots` grows unbounded.** One row per keyword x app x capture. No partition strategy, no TTL, no pruning job. | Unbounded table growth |
| DB4 | P2 | **`app_analytics` grows unbounded.** Each recompute appends new rows (many-to-one). No pruning visible. | Unbounded table growth |
| DB5 | P2 | **Connection pool may exhaust.** `pool_size=5, max_overflow=10` = 15 max connections. With 15 concurrent quick-refresh workers plus scheduler jobs, pool exhaustion is possible. | Connection errors |
| DB6 | P2 | **30+ Python-side-only defaults.** Columns like `is_active`, `role`, `plan_code`, `currency`, `is_free` have ORM defaults but no `server_default`. Raw SQL inserts bypass these. | Data corruption via SQL |
| DB7 | P3 | **Synchronous SQLAlchemy despite `asyncpg` URL.** The URL uses `postgresql+asyncpg://` but the code strips `+asyncpg` and uses synchronous `psycopg2`. Misleading config. | Confusion, no async benefit |

---

### PERFORMANCE

| # | Sev | Finding | Impact |
|---|-----|---------|--------|
| P1 | P1 | **Synchronous LLM calls in request handlers.** `/apps/{id}/autopsy`, `/apps/{id}/review-intelligence` (with force), `/ideas/generate` all block a worker thread for 10-30s. | Worker starvation |
| P2 | P1 | **`POST /scrape/all` is synchronous full-catalog scrape.** Holds a worker thread for potentially hours. | Worker starvation |
| P3 | P2 | **Blocking HTTP client.** `apple_http_client.py` uses `urllib.request` with `Connection: close`. No connection pooling, no HTTP/2, no keep-alive. Every request opens a fresh TCP connection. | 2-3x slower than async client |
| P4 | P2 | **Circuit breaker is not thread-safe.** `_consecutive_403s` uses module-level globals modified via `global`. Race condition under concurrent `asyncio.to_thread` calls. | Counter desync |
| P5 | P2 | **N+1 in `get_keyword_opportunities`.** Per-keyword COUNT query on `AppKeyword` for each of 50 keywords. | 50 extra queries per call |
| P6 | P2 | **N+1 in keyword_rank_tracker `_update_app_keyword_positions`.** Per-app queries for 20 results x 50 keywords = up to 2000 queries per run. | Slow rank tracking |
| P7 | P2 | **No caching for `/categories`.** Queried on every page load, rarely changes. | Unnecessary DB hits |

---

### DEAD CODE

| # | Sev | Finding | Location |
|---|-----|---------|----------|
| DC1 | P3 | `/trending/v2` is 100% copy-paste of `/trending` | `routes.py` |
| DC2 | P3 | `save_rankings()` method never called | `tasks.py` |
| DC3 | P3 | `_check_fresh_riser_eligibility` + `_calculate_fresh_riser_scores` orphaned (batch version inlines) | `engine.py` |
| DC4 | P3 | `_fetch_icons` in AppStoreSearchScraper never called | `appstore_search_scraper.py` |
| DC5 | P3 | Dead Playwright browser init in AppStoreScraper (wastes 200MB if called) | `appstore.py` |
| DC6 | P3 | `self.weights = SCORING_WEIGHTS` stored but never used | `engine.py` |
| DC7 | P3 | `_initial_scrape_background` commented out | `main.py` |
| DC8 | P3 | `SCORING_WEIGHTS`, `CATEGORY_WEIGHTS`, `KEYWORD_DIFFICULTY_THRESHOLDS` imported but unused | `engine.py` |
| DC9 | P3 | `DailyReport` table largely superseded by `DailyOpportunity` | `models.py` |
| DC10 | P3 | Deprecated Pydantic v1 API: `app.dict()`, `app_update.dict(exclude_unset=True)` | `routes.py` |
| DC11 | P3 | `backfill_keyword_structure.py` — one-time migration utility living in services | `services/` |
| DC12 | P3 | `keyword_quality_backfill.py` — one-time backfill utility living in services | `services/` |

---

### DUPLICATED BUSINESS LOGIC

| # | Sev | Finding | Files |
|---|-----|---------|-------|
| DUP1 | P2 | **IR ratios duplicated.** `download_estimator.py` and `install_estimator.py` both contain `_CATEGORY_IR_RATIO` dicts that can go out of sync. | `services/download_estimator.py`, `services/install_estimator.py` |
| DUP2 | P2 | **Opportunity score formula duplicated.** `opportunity_service.py` and `keyword_discovery_service.py` each implement their own version. | `services/opportunity_service.py`, `services/keyword_discovery_service.py` |
| DUP3 | P2 | **CTR tables duplicated.** Same hardcoded click-through rates in `competitor_keyword_service.py` and `keyword_extraction_service.py`. | `services/competitor_keyword_service.py`, `services/keyword_extraction_service.py` |
| DUP4 | P3 | **Search volume/difficulty proxy formulas duplicated** across multiple keyword services. | Multiple keyword services |

---

## PART 3: FINDINGS BY TABLE

### Tables That Nothing Populates / Drains

| Table | Issue |
|-------|-------|
| `keyword_queue` | Written to by `keyword_discovery_engine`, **never read or processed** |
| `discovery_queue` (done/failed rows) | Accumulate forever, no cleanup job |

### Tables Missing Dedicated Scheduler Jobs

| Table | Currently Populated By | Risk |
|-------|----------------------|------|
| `app_metric_snapshots` | Side-effect of `hourly_scoring` | If scoring job fails, no snapshots |
| `app_analytics` | Side-effect of `sentiment_analysis` | No direct scheduler job, no pruning |
| `categories` | Bootstrap only | No ongoing refresh |

---

## PART 4: COMPLETE ROADMAP

### Phase A: STABILIZATION (Week 1-2)
*Fix critical security and data integrity issues that make the platform unsafe for production.*

| # | Task | Fixes | Priority |
|---|------|-------|----------|
| A1 | Fix `_NoOpEnforcer` to deny access instead of granting unlimited | S1 | P0 |
| A2 | Enforce `access_premium` on premium endpoints | S2 | P0 |
| A3 | Default unknown plan codes to "free" not "pro" | S3 | P0 |
| A4 | Add authentication to all 13 unprotected mutating endpoints | S4 | P0 |
| A5 | Remove fabricated `search_volume = app_count * 850` | D1, D2, F11, F12 | P0 |
| A6 | Remove fabricated `trend` static map | D3, F13 | P0 |
| A7 | Replace fabricated metrics with honest "no data" / "estimated" labels | F14, F6 | P1 |
| A8 | Fix JWT secret to fail-fast if not set in production | S5 | P1 |
| A9 | Fix admin token default (require in production) | S8 | P1 |
| A10 | Fix sidebar hardcoded "Admin" identity | D5 | P1 |
| A11 | Add trial expiration enforcement | S6 | P2 |
| A12 | Add rate limiting to password change | S7 | P2 |

### Phase B: DATA INTEGRITY (Week 2-3)
*Ensure all displayed metrics are truthful and consistent.*

| # | Task | Fixes | Priority |
|---|------|-------|----------|
| B1 | Unify `trend_score` formula (pick one, deprecate other) | D4 | P1 |
| B2 | Fix `rank_velocity` to divide by time span, not data point count | D6 | P2 |
| B3 | Fix `calculate_category_growth` to compare periods | D7 | P2 |
| B4 | Add rating validation (1-5) in schema + ingestion | D8 | P2 |
| B5 | Fix `has_in_app_purchases` filter (compare correctly) | F7 | P1 |
| B6 | Fix `min_probability=0.0` falsy check | F23 | P1 |
| B7 | Fix dashboard trending count to use `stats.trending_apps_count` | F1 | P1 |
| B8 | Fix `/keywords/enhanced` classification total count | F15 | P1 |
| B9 | Remove legacy duplicate columns (Keyword.search_volume/difficulty/trend, AppKeyword.position) | D10 | P3 |
| B10 | Reconcile `primary_category` string vs `category_id` FK | D9 | P2 |
| B11 | Add `ondelete="CASCADE"` to 11 missing FK constraints | DB2 | P1 |

### Phase C: SYNCHRONIZATION (Week 3-4)
*Eliminate job overlaps, race conditions, and dead paths.*

| # | Task | Fixes | Priority |
|---|------|-------|----------|
| C1 | Split `hourly_scoring` mega-job into dedicated jobs | J5 | P1 |
| C2 | Deduplicate `daily_reports` writes (single writer) | F25 | P2 |
| C3 | Consolidate 3 keyword pruning mechanisms into 1 | J8 | P2 |
| C4 | Add `discovery_queue` "scraping" status recovery job | J4 | P1 |
| C5 | Add `discovery_queue` cleanup job (purge done/failed > 7d) | J7 | P2 |
| C6 | Remove or drain `keyword_queue` dead queue | J6 | P2 |
| C7 | Remove redundant `feature_gap` job (already in hourly_scoring) | F27 | P2 |
| C8 | Remove `/trending/v2` duplicate endpoint | DC1 | P3 |
| C9 | Remove dead code (DC2-DC10) | DC2-DC10 | P3 |
| C10 | Update MASS_KEYWORDS year from 2024 to dynamic | J10 | P2 |

### Phase D: PERFORMANCE (Week 4-5)
*Resolve scaling bottlenecks and resource waste.*

| # | Task | Fixes | Priority |
|---|------|-------|----------|
| D1 | Make LLM endpoints async (autopsy, review-intelligence, ideas/generate) | P1, F30, F31 | P1 |
| D2 | Add persistent job store (PostgreSQL-backed APScheduler) | J1 | P1 |
| D3 | Add index on `apps.description` (GIN trigram) for ILIKE search | F8 | P2 |
| D4 | Replace `query.count()` + `query.offset().limit()` with `SELECT count(*) OVER()` | F10 | P2 |
| D5 | Convert classification filter to SQL instead of Python | F16 | P2 |
| D6 | Convert keyword trend aggregation to SQL GROUP BY | F17 | P2 |
| D7 | Fix N+1 in `get_keyword_opportunities` (batch COUNT) | P5 | P2 |
| D8 | Fix N+1 in `_update_app_keyword_positions` (batch lookup) | P6 | P2 |
| D9 | Add caching for `/categories` endpoint | P7 | P2 |
| D10 | Replace `urllib` with `httpx` async client for Apple API | P3 | P2 |
| D11 | Drop ~19 redundant database indexes | DB1 | P2 |
| D12 | Reduce `blowing_up_compute` from 15min to 30min or 1h | J11 | P3 |
| D13 | Increase `discovery_charts` batch_size from 12 to 60 | F20 | P2 |
| D14 | Add thread-safe circuit breaker (threading.Lock) | P4 | P2 |
| D15 | Add `_with_timeout` to `bootstrap_data` job | J12 | P3 |

### Phase E: SCALE TO 500K+ APPS (Week 5-8)
*Re-architect jobs and queries for 10x data volume.*

| # | Task | Fixes | Priority |
|---|------|-------|----------|
| E1 | Rewrite `hourly_reviews_ratings` with tiered refresh (HOT=1h, WARM=6h, COLD=24h) | J2 | P1 |
| E2 | Rewrite `full_metadata` with concurrent scraping + tiered batches | J3 | P1 |
| E3 | Rewrite `keyword_discovery_daily` and `phase1_daily` with bounded batches | J9 | P2 |
| E4 | Add partition strategy for `keyword_search_snapshots` (by month) | DB3 | P2 |
| E5 | Add partition strategy for `app_metric_snapshots` (by month) | DB3 | P2 |
| E6 | Add retention/pruning for `app_analytics` (keep last 90 days) | DB4 | P2 |
| E7 | Implement connection pool monitoring (log pool exhaustion) | DB5 | P2 |
| E8 | Build Competitors page (currently Coming Soon placeholder) | F-Competitors | P2 |
| E9 | Add `server_default` to all columns with Python-only defaults | DB6 | P3 |
| E10 | Migrate inline DDL to proper Alembic migrations | main.py | P3 |

---

## PART 5: FABRICATED DATA INVENTORY

Every metric below is displayed to users as if it is real data. None are based on actual measurements.

| # | Metric | Where Fabricated | Formula | Shown Where |
|---|--------|-----------------|---------|-------------|
| FAB1 | **search_volume** (keywords) | `engine.py:update_keyword_metrics` | `app_count * 850` | Keywords page, keyword detail, opportunities |
| FAB2 | **difficulty** (keywords) | `engine.py:update_keyword_metrics` | `min(app_count, 60)` | Keywords page, keyword detail |
| FAB3 | **trend** (keywords) | `engine.py:update_keyword_metrics` | Static map: "ai"=8.5, "gpt"=8.0, default=3.0 | Keywords page |
| FAB4 | **search_volume** (per-app keywords) | `competitor_keyword_service.py`, `keyword_extraction_service.py` | `log10(iTunes_result_count) / log10(50) * 100` | App keyword tabs |
| FAB5 | **difficulty** (per-app keywords) | `competitor_keyword_service.py` | Average ratings + review counts of top 10 results | App keyword tabs |
| FAB6 | **CTR percentages** | `competitor_keyword_service.py`, `keyword_extraction_service.py` | Hardcoded table: rank1=30%, rank2=15%, rank3=10% | Traffic score calculations |
| FAB7 | **Download estimates** | `download_estimator.py`, `install_estimator.py` | Rank curve * hardcoded install-to-review ratios (games=1500, social=1000, etc.) | App detail, dashboard |
| FAB8 | **Revenue estimates** | `revenue_estimator.py` | Fabricated installs * hardcoded ARPU (productivity=$2.50, games=$1.50) * hardcoded conversion (3%) | App detail |
| FAB9 | **Bootstrap rankings** | `bootstrap_data_service.py` | 3 identical snapshots at now-4d/now-2d/now with same rank | Rank history chart |
| FAB10 | **"AI summaries"** (opportunities) | `opportunity_of_day_service.py`, `weekly_opportunities_service.py` | Rule-based string templates, not LLM-generated | Opportunity cards |
| FAB11 | **Synthetic ad creatives** | `ad_intelligence_service.py` | Heuristic detection with `{"inferred": True}` flag stored as detected ads | Ad Intelligence page |
| FAB12 | **ads_presence** (keywords) | `routes.py:GET /keywords/enhanced` | Hardcoded `0.0` for every keyword | Keywords page |
| FAB13 | **feature_gap_count** (keywords) | `routes.py:GET /keywords/enhanced` | Hardcoded `0` for every keyword | Keywords page |
| FAB14 | **Analytics fallback** | `routes.py:GET /apps/{id}/analytics` | All-zeros object with `id=0`, `computed_at=now()` | App detail analytics tab |

### Fabrication Chain
```
Hardcoded IR ratios + Rank curves
        |
        v
Install estimates (FAB7) -----> Revenue estimates (FAB8)
        |                               |
        v                               v
MetricSnapshots table          App.estimated_revenue_*
        |
        v
CampaignTrackingService (uses fabricated metric snapshots for signal detection)
        |
        v
GrowthEvents table (campaign classifications based on fabricated metrics)
```

---

## APPENDIX A: UNUSED/REDUNDANT INDEXES TO DROP

```sql
-- 19 redundant indexes (save ~10-15% write overhead)
DROP INDEX IF EXISTS idx_membership_user;
DROP INDEX IF EXISTS idx_sub_workspace;
DROP INDEX IF EXISTS idx_ak_app_id;
DROP INDEX IF EXISTS idx_market_weakness_app;
DROP INDEX IF EXISTS idx_feature_gap_app;
DROP INDEX IF EXISTS idx_weekly_opp_week;
DROP INDEX IF EXISTS idx_kss_keyword;
DROP INDEX IF EXISTS idx_dp_source_key;
DROP INDEX IF EXISTS idx_km_keyword_id;
DROP INDEX IF EXISTS idx_aki_app;
DROP INDEX IF EXISTS idx_adk_app;
DROP INDEX IF EXISTS idx_ktrend_keyword;
DROP INDEX IF EXISTS idx_ams_app_id;
DROP INDEX IF EXISTS idx_creative_app;
DROP INDEX IF EXISTS idx_campaign_app;
DROP INDEX IF EXISTS idx_growth_app;
-- Plus 3 duplicate indexes from column-level index=True + __table_args__
-- on DiscoveryQueue.added_at, DiscoveryQueue.status, KeywordQueue.added_at, KeywordQueue.status
```

## APPENDIX B: SCHEDULER JOB INVENTORY

| # | Job ID | Interval | Timeout | Status |
|---|--------|----------|---------|--------|
| 1 | `bootstrap_data` | One-shot (+1min) | None | OK |
| 2 | `trending_compute` | 10min | 300s | OK |
| 3 | `blowing_up_compute` | 15min | 600s | Wasteful (should be 30-60min) |
| 4 | `opportunity_compute` | 1h | 600s | Overlaps with hourly_scoring |
| 5 | `weekly_opportunities_compute` | 6h | 600s | OK |
| 6 | `discovery_keywords` | 6h | 3600s | Partially redundant with mass_discovery |
| 7 | `discovery_charts` | 2h | 1800s | batch_size too small |
| 8 | `discovery_developer` | 12h | 1800s | OK |
| 9 | `queue_processor` | 30min | 3600s | "scraping" status leak |
| 10 | `mass_discovery_light` | 6h | 3600s | Overlaps with discovery_keywords |
| 11 | `tier_reclassify` | 6h | 600s | OK |
| 12 | `enrich_hot` | 1h | 1800s | OK |
| 13 | `enrich_warm` | 6h | 3600s | OK |
| 14 | `enrich_cold` | 24h | 3600s | Timeout too short |
| 15 | `hourly_reviews_ratings` | 1h | 3600s | Cannot scale |
| 16 | `hourly_scoring` | 1h | 3600s | Mega-job, should be split |
| 17 | `full_metadata` | 6h | 7200s | Cannot scale |
| 18 | `keyword_rank_tracker` | 6h | 3600s | OK |
| 19 | `keyword_intelligence` | 12h | 7200s | OK |
| 20 | `keyword_scoring` | 6h | 3600s | Redundant with hourly_scoring |
| 21 | `keyword_discovery` | 24h | 7200s | Writes to dead queue |
| 22 | `keyword_discovery_daily` | 24h | 7200s | Cannot scale |
| 23 | `keyword_discovery_phase1_daily` | 24h | 7200s | Cannot scale |
| 24 | `keyword_cleanup_daily` | 24h | 600s | Partially redundant (3 pruning mechanisms) |
| 25 | `keyword_quality_pruning` | 24h | 600s | Partially redundant (3 pruning mechanisms) |
| 26 | `review_scraper` | 6h | 3600s | OK |
| 27 | `sentiment_analysis` | 1h | 600s | OK |
| 28 | `feature_gap` | 2h | 1800s | Redundant with hourly_scoring |

## APPENDIX C: MODEL COUNT SUMMARY

| Category | Count |
|----------|-------|
| Auth/Billing models | 5 (User, Workspace, Membership, Subscription, WorkspaceUsage) |
| Core app models | 6 (Category, App, Ranking, Review, AppVersion, AppAnalytics) |
| Keyword models | 7 (Keyword, KeywordMetrics, AppKeyword, KeywordSearchSnapshot, KeywordQueue, AppDiscoveredKeyword, KeywordTrend) |
| Scoring models | 4 (Opportunity, AppTrendingScore, AppBlowingUpScore, AppMetricSnapshot) |
| Intelligence models | 4 (AppMarketWeakness, FeatureGap, AppKeywordIntelligence, AppIdea) |
| Ad/Campaign models | 3 (AdCreative, AdCampaign, GrowthEvent) |
| Pipeline models | 2 (DiscoveryQueue, DiscoveryProgress) |
| Report models | 3 (DailyReport, DailyOpportunity, WeeklyOpportunity) |
| **Total** | **34** |
