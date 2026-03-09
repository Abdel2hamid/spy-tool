# Session Memory

Template and log for future AI coding sessions. Each session summary should be appended below.

---

## How to Use This File

At the start of a new coding session, read this file to understand recent changes.
At the end of a session (or when asked to "remember"), append a new entry using the template below.

---

## Session Entry Template

```
---

## Session: YYYY-MM-DD

**Summary:** One sentence description of what was accomplished.

**Changes Made:**
- Brief description of each change

**Files Modified:**
- `path/to/file.py` — what changed
- `path/to/file.tsx` — what changed

**Files Created:**
- `path/to/new_file.py` — what it does

**Features Added:**
- Feature name: how it works

**Bugs Fixed:**
- Bug description: how it was fixed

**Next Tasks:**
- What to do next session

**Notes / Gotchas:**
- Anything important to remember about this session's changes
```

---

## Session Log

---

## Session: 2026-03-08 (Session 1 — Project Kickoff & Core Features)

**Summary:** Built the entire AppStore Spy tool from scratch — backend scraping, scoring engine, all API routes, and Next.js frontend.

**Features Added:**
- App discovery via iTunes Search API and top charts RSS feeds
- Full app metadata scraping (iTunes Lookup API)
- Version history scraping from App Store HTML with JSON extraction
- Review collection from iTunes RSS API (paginated)
- Chart rankings with rank velocity computation
- `ScoringEngine` with 7 composite metrics
- Market weakness analysis (per-country negative review ratios)
- Feature gap NLP mining (regex trigger patterns + synonym normalization)
- AI app idea generator (3 patterns: feature_gap, weak_market, keyword_gap)
- APScheduler with 5 recurring jobs
- 30+ FastAPI endpoints
- Next.js 14 frontend: Dashboard, Apps browser, App detail (8 tabs), Trending, Opportunities, AI Ideas, Keywords, Rankings pages
- Advanced app filtering system (19 parameters)

**Files Created (key files):**
- `backend/app/main.py` — FastAPI app + lifespan
- `backend/app/models/models.py` — 14 SQLAlchemy models
- `backend/app/models/schemas.py` — Pydantic schemas
- `backend/app/api/routes.py` — All API endpoints
- `backend/app/scrapers/appstore.py` — iTunes search + charts
- `backend/app/scrapers/app_details.py` — Full app scraper
- `backend/app/scoring/engine.py` — Scoring engine
- `backend/app/scoring/feature_gaps.py` — NLP analyzer
- `backend/app/scoring/idea_generator.py` — AI idea generator
- `backend/app/workers/tasks.py` — ScraperWorker + ScoringWorker
- `backend/app/workers/scheduler.py` — APScheduler jobs
- `frontend/src/app/apps/[id]/page.tsx` — App detail (8 tabs, ~1250 lines)
- `frontend/src/lib/api.ts` — All TypeScript types + API functions

---

## Session: 2026-03-08 (Session 2 — Version History Fix)

**Summary:** Fixed version history scraping after Apple migrated to Svelte-rendered pages.

**Bugs Fixed:**
- Version history showed only 1 version (current): Apple changed page rendering — the `?see-all=versions` URL returns 404, and CSS class `.version-history__item` no longer exists.

**Fix Applied:**
- `backend/app/scrapers/app_details.py:get_app_versions()`:
  - Now fetches the main app page URL (not `?see-all=versions`)
  - Searches all `<script>` tags for embedded JSON containing `"mostRecentVersion"`
  - Uses recursive `_find_key()` helper to navigate the JSON tree
  - Path: `mostRecentVersion → seeAllAction → pageData → shelves[0] → items`
  - Each item: `primarySubtitle` = version, `secondarySubtitle` = date, `text` = release notes
  - Date parsing handles format: `"Thu Mar 05 2026 10:54:19 GMT+0000 (...)"`
  - BeautifulSoup CSS fallback kept but likely broken on current pages

**Key Gotcha:** Apple's App Store pages embed version data in a `<script>` tag as JSON, not in the HTML DOM. The JSON structure changes periodically. The recursive `_find_key()` approach is more resilient than hard-coded path navigation.

---

## Session: 2026-03-08 (Session 3 — Real App Store Search Scraping)

**Summary:** Implemented complete Playwright-based keyword rank tracking system with sponsored detection and keyword intelligence.

**Features Added:**
1. **Keyword Rank Tracker** (`backend/app/jobs/keyword_rank_tracker.py`): Scrapes live App Store search results using Playwright. Saves to `keyword_search_snapshots` table. Updates `AppKeyword.position` for tracked apps.
2. **AppStoreSearchScraper** (`backend/app/scrapers/appstore_search_scraper.py`): Playwright Chromium browser scraper. Sponsored detection via DOM inspection. Icon URLs enriched via iTunes batch lookup after extraction.
3. **KeywordIntelligenceService** (`backend/app/services/keyword_intelligence.py`): Scores per-app keyword intelligence from snapshots. Computes primary_keyword, confidence, organic/ad keyword lists, traffic mix.
4. **New DB table:** `keyword_search_snapshots` (14 columns, multiple indexes)
5. **New API endpoints:** 5 new endpoints under `/keyword-tracker/` prefix
6. **Frontend: Keywords tab** added as 8th tab on app detail page with traffic mix bar, keyword tables, manual scan input

**Critical Bug Fixed:**
- App Store search URL: `?term=productivity` → 404 (broke in early 2026). Fixed to `?q=productivity`.

**Key Gotcha:** Apple's App Store search images are lazy-loaded with `loading="lazy"` and no `srcset` or `data-src`. Headless Playwright cannot trigger lazy loading. Solution: After extracting app IDs, do a separate batch iTunes Lookup API call to get `artworkUrl100`.

**Files Modified:**
- `backend/app/models/models.py` — Added `KeywordSearchSnapshot`
- `backend/app/models/schemas.py` — Added 8 new schemas
- `backend/app/workers/scheduler.py` — Added `job_keyword_rank_tracker`
- `backend/app/api/routes.py` — Added 5 new endpoints
- `frontend/src/lib/api.ts` — Added `KeywordIntelligence` types + 2 functions
- `frontend/src/app/apps/[id]/page.tsx` — Added `KeywordIntelligenceTab` component (8th tab)

**Files Created:**
- `backend/app/scrapers/appstore_search_scraper.py`
- `backend/app/jobs/__init__.py`
- `backend/app/jobs/keyword_rank_tracker.py`
- `backend/app/services/__init__.py`
- `backend/app/services/keyword_intelligence.py`

---

## Session: 2026-03-08 (Session 4 — AI Context Memory System)

**Summary:** Created `AI_CONTEXT/` folder with 11 comprehensive documentation files for future AI session context.

**Files Created:**
- `AI_CONTEXT/PROJECT_SUMMARY.md`
- `AI_CONTEXT/ARCHITECTURE_OVERVIEW.md`
- `AI_CONTEXT/FEATURES_INDEX.md`
- `AI_CONTEXT/CODEBASE_MAP.md`
- `AI_CONTEXT/DATA_PIPELINE.md`
- `AI_CONTEXT/SCRAPERS_INDEX.md`
- `AI_CONTEXT/API_ENDPOINTS.md`
- `AI_CONTEXT/DATABASE_SCHEMA.md`
- `AI_CONTEXT/KNOWN_LIMITATIONS.md`
- `AI_CONTEXT/NEXT_STEPS.md`
- `AI_CONTEXT/SESSION_MEMORY.md` (this file)

Also created: `PRODUCT_STRATEGY_REPORT.md` at repository root (product strategy analysis).

---

## Session: 2026-03-08 (Session 6 — Railway Deployment Prep)

**Summary:** Slimmed requirements for fast Railway builds by splitting into prod vs dev packages and fixing module-level Playwright/numpy imports.

**Changes Made:**
- Removed `numpy`, `scikit-learn`, `playwright`, `lxml`, `asyncpg`, `alembic` from production `requirements.txt`
- Created `requirements-dev.txt` (includes all heavy packages for local dev)
- Fixed `appstore.py`: module-level `from playwright.async_api import ...` replaced with guarded try/except + lazy import inside `init()`. Type hints changed to `Optional[Any]`.
- Removed dead `import numpy as np` from `scoring/engine.py` (numpy was never used)
- Created `Procfile` for Railway: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Created `DEPLOYMENT.md` explaining which requirements file Railway uses, env vars, and what's excluded

**Files Modified:**
- `backend/requirements.txt` — production slim (8 packages, no Playwright/numpy/sklearn)
- `backend/app/scrapers/appstore.py` — lazy Playwright import
- `backend/app/scoring/engine.py` — removed dead numpy import

**Files Created:**
- `backend/requirements-dev.txt` — full dev deps
- `backend/Procfile` — Railway start command
- `backend/DEPLOYMENT.md` — Railway deployment guide

**Verified:** `python3` boot test with playwright/numpy/sklearn/lxml/asyncpg/alembic blocked → clean boot, 45 routes registered.

**Railway Commands:**
- Build: `pip install -r requirements.txt` (auto-detected)
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Notes / Gotchas:**
- Keyword rank tracking (Playwright job) will log an error and skip gracefully when Playwright isn't installed — API is unaffected
- `DATABASE_URL` env var from Railway Postgres is `postgresql://...` — the app strips `+asyncpg` suffix automatically so both formats work
- `appstore_backup.py` is a stale unused file (never imported) — it still has a top-level Playwright import but causes no issues since it's never imported

---

## Session: 2026-03-09 (Session 7 — Railway Python Version Pin)

**Summary:** Fixed Railway build failure caused by Python 3.13 breaking pydantic-core by pinning the environment to Python 3.11.9.

**Bug Fixed:**
- Railway defaulted to Python 3.13; `pydantic-core` (Pydantic v2 compiled Rust extension) has no pre-built wheel for 3.13 at pinned versions → build failure.

**Fix Applied:**
- Created `runtime.txt` at **repository root** (`/appstore-spy-tool/runtime.txt`) containing exactly `python-3.11.9`
- Railway Nixpacks builder reads this file to pin the Python version
- Updated `backend/DEPLOYMENT.md` with a "Python Version" section explaining the constraint

**Files Created:**
- `runtime.txt` (repo root, NOT inside `backend/`) — `python-3.11.9`

**Files Modified:**
- `backend/DEPLOYMENT.md` — added Python Version section at top

**Key Gotcha (corrected):** When the Railway service root is set to `backend/`, Nixpacks resolves all config files relative to `backend/`. A `runtime.txt` at the repo root is ignored. All three version-pin files (`runtime.txt`, `.python-version`, `nixpacks.toml`) must live inside `backend/`. `nixpacks.toml` is the most reliable override because it explicitly sets the Nix package (`python311`) and the start command.

---

## Session: 2026-03-09 (Session 8 — Dashboard API Mismatch Fix)

**Summary:** Fixed dashboard showing no data on Railway due to Next.js rewrite proxy pointing to hardcoded `localhost:8000` instead of the deployed backend URL.

**Root Cause:**
- Browser calls relative URLs: `fetch('/api/v1/dashboard/stats')`
- `next.config.js` rewrites `/api/:path*` → `http://localhost:8000/api/:path*`
- On Railway, `localhost:8000` is unreachable (backend is a separate service at a different URL)
- All API calls silently failed; dashboard `.catch()` returned zeros — looked like "no data"
- "Direct requests to guessed endpoints return `{"detail":"Not Found"}`" = manual tests hit the backend without the `/api/v1` prefix

**Fix:**
- `frontend/next.config.js`: rewrite destination changed from hardcoded `http://localhost:8000` to `${process.env.BACKEND_URL || 'http://localhost:8000'}/api/:path*`
- `BACKEND_URL` is a **server-side** env var (NOT `NEXT_PUBLIC_`) — set it in Railway Frontend service to the backend Railway URL (no trailing slash, no `/api/v1`)

**Files Modified:**
- `frontend/next.config.js` — rewrite destination now uses `BACKEND_URL` env var
- `backend/DEPLOYMENT.md` — added Frontend service variables section explaining `BACKEND_URL`

**Key Gotchas:**
- `BACKEND_URL` must NOT include trailing slash or path: `https://backend-xxx.railway.app` ✓
- `NEXT_PUBLIC_API_URL` should NOT be set on Railway (leave unset so it defaults to `/api/v1`)
- If `NEXT_PUBLIC_API_URL` IS set, it must include `/api/v1`: `https://backend-xxx.railway.app/api/v1`; without it every endpoint returns 404
- All routing is: Browser → `/api/v1/X` → Next.js proxy → `$BACKEND_URL/api/v1/X` → FastAPI

**Next Railway Step:** In Railway → Frontend Service → Variables, add `BACKEND_URL=https://your-backend-service.railway.app` then redeploy the frontend.

---

## Session: 2026-03-09 (Session 9 — API_BASE normalization fix)

**Summary:** Fixed `api.ts` `API_BASE` to always include `/api/v1` regardless of whether `NEXT_PUBLIC_API_URL` contains it or not.

**Root Cause:**
- `const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1'`
- If Railway sets `NEXT_PUBLIC_API_URL=https://backend.railway.app` (no `/api/v1`), every call becomes `https://backend.railway.app/dashboard/stats` — missing prefix → FastAPI 404 on all dashboard endpoints

**Fix (`frontend/src/lib/api.ts` line 1):**
```js
const _rawBase = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/+$/, '');
const API_BASE = _rawBase === ''
  ? '/api/v1'
  : _rawBase.endsWith('/api/v1')
    ? _rawBase
    : `${_rawBase}/api/v1`;
```
All three cases handled correctly:
- Unset → `/api/v1` (relative, through Next.js proxy)
- `https://backend.railway.app` → `https://backend.railway.app/api/v1` ✓
- `https://backend.railway.app/api/v1` → `https://backend.railway.app/api/v1` ✓ (idempotent)

**Files Modified:**
- `frontend/src/lib/api.ts` — `API_BASE` normalization

---

## Session: 2026-03-09 (Session 10 — Bootstrap Endpoint for Empty Railway DB)

**Summary:** Added `POST /api/v1/admin/bootstrap` to populate a fresh Railway database in one call.

**Root Cause of Empty Dashboard:**
- Railway Postgres is freshly provisioned → zero rows in all tables
- Scheduler `discovery` job first runs +12h after deploy, `full_metadata` +6h
- `POST /scrape/all` is useless on an empty DB (no apps to scrape)
- No endpoint existed to seed the database from scratch

**New Endpoints Added (`backend/app/api/routes.py`):**
- `POST /api/v1/admin/bootstrap` — runs full pipeline in background (discovery → full scrape → scoring), returns immediately. Returns 409 if already running.
- `GET /api/v1/admin/bootstrap/status` — shows `bootstrap_running`, total_apps, keywords, reviews counts

**Pipeline in bootstrap:**
1. `run_scrape_task()` — keyword search (10 keywords × 50 results) + top charts + full details for every discovered app
2. `run_scoring_task()` — opportunities, market weakness, feature gaps, ideas, install/revenue estimates

**Other fixes in routes.py:**
- Added `BackgroundTasks` to fastapi imports
- Moved `import asyncio` to module-level (removed duplicate inline imports)

**Files Modified:**
- `backend/app/api/routes.py` — added bootstrap endpoints, fixed imports

---

## Session: 2026-03-09 (Session 12 — Opportunity of the Day: Big Brand Exclusion + Feasibility Scoring)

**Summary:** Fixed "Opportunity of the Day" to never surface apps dominated by major companies; rewrote scoring to 45% attractiveness + 55% feasibility.

**Root Cause:**
- `generate_opportunity_of_day()` ranked purely by `attractiveness_score` → ChatGPT, Gemini, and other mega-apps with high ratings and reviews always won.

**Changes Made:**
- Added module-level constants to `engine.py`: `_BIG_BRAND_DEVELOPERS` (frozenset, 60+ brands), `_BIG_BRAND_APP_KEYWORDS` (tuple of brand name fragments), dominance thresholds (`_BEHEMOTH_REVIEWS=500000`, `_ENTRENCHED_REVIEWS=100000`, `_CHART_DOMINATOR_REVIEWS=50000`)
- Added 4 methods to `ScoringEngine`:
  - `_is_excluded_big_brand(app)` → `(bool, reason_str)` — O(1) frozenset lookup + substring match
  - `_is_dominated_market(app)` → `(bool, reason_str)` — 3 thresholds: behemoth, entrenched+4.5★, chart dominator+rank≤3
  - `calculate_feasibility_score(app, competition_score)` → `(float, dict)` — 5-component 100pt system: review scarcity (25), keyword competition (25), feature gap count (20), rating weakness (15), rank accessibility (15)
  - `_generate_winnability_recommendation(feasibility, details)` → human-readable text
- Rewrote `generate_opportunity_of_day()`: hard exclusions first → `combined = attractiveness*0.45 + feasibility*0.55`
- Extended `OpportunityOfDayResponse` schema with optional fields: `attractiveness_score`, `feasibility_score`, `feasibility_details`

**Files Modified:**
- `backend/app/scoring/engine.py` — exclusion constants, 4 new methods, updated generate_opportunity_of_day
- `backend/app/models/schemas.py` — extended OpportunityOfDayResponse

---

## Session: 2026-03-09 (Session 13 — Performance + Freshness Priority System)

**Summary:** Added DB indexes, dashboard caching, pagination, freshness scoring, and discovery queue priority for newly released apps.

**Changes Made:**
- `App` model: added `freshness_score` column + 8 new DB indexes (rating, reviews, rank, release_date, created_at, freshness, developer, primary_category)
- `main.py`: idempotent migrations for `freshness_score` column + all 8 indexes (`ALTER TABLE ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`)
- `routes.py`: 60-second TTL in-process dashboard cache (`_DASHBOARD_CACHE` dict + `time.monotonic()`), `page` param for 1-based pagination, `fresh_only`/`min_freshness_score` filters, `sort_by=freshness_score`, `new_apps_last_30_days`/`new_apps_last_90_days` in dashboard stats
- `tasks.py`: `_compute_freshness_score(release_date)` (100=<30d, 80=<60d, 60=<90d, 40=<180d, 20=<365d, 0=>1yr), saves after scrape, workers ordered by `freshness_score DESC NULLS LAST`, `update_opportunities()` limit 100→200 + ordered by freshness
- `discovery_engine.py`: `_fetch_keyword_with_dates()` (fetches `releaseDate` from iTunes), `_freshness_priority()` (priority 5=<30d, 4=<90d, 2=older), queue processing ordered by `priority DESC, added_at DESC`, metrics now include `new_apps_last_30_days`/`new_apps_last_90_days`
- `schemas.py`: `DashboardStatsResponse` extended with `new_apps_last_30_days`, `new_apps_last_90_days`
- `backend/DEPLOYMENT.md`: added Performance & Scalability section

**Files Modified:**
- `backend/app/models/models.py` — freshness_score column + 8 indexes
- `backend/app/main.py` — 9 migrations
- `backend/app/api/routes.py` — cache, pagination, freshness filters, new stats fields
- `backend/app/workers/tasks.py` — freshness compute + ordering
- `backend/app/workers/discovery_engine.py` — freshness-aware discovery
- `backend/app/models/schemas.py` — DashboardStatsResponse extended
- `backend/DEPLOYMENT.md` — performance docs

---

## Session: 2026-03-09 (Session 14 — Frontend Crash Fixes)

**Summary:** Fixed 5 frontend pages crashing (Trending, Opportunities, AI Opportunities, Niche Radar, Keywords) due to wrong API URL construction and missing null guards.

**Root Causes:**
1. Server page files used `process.env.NEXT_PUBLIC_API_URL` without `/api/v1` suffix normalization → all fetches returned `{"detail":"Not Found"}` (valid JSON, so `.catch()` didn't fire)
2. Error objects were passed as array props → `.filter()/.map()/.slice()` crashed at runtime
3. `api.ts` used relative `/api/v1` in server context → Node fetch requires absolute URLs
4. `idea.reasoning` and `idea.related_app_ids` could be null → `.length` crash
5. `niche.keywords` could be null → `.slice()` crash

**Fixes Applied:**
- `api.ts`: replaced `API_BASE` constant with `_resolveApiBase()` — detects server vs browser context, uses `BACKEND_URL` env var on server, `NEXT_PUBLIC_API_URL` on client, normalizes trailing slashes and `/api/v1` suffix
- `trending/page.tsx`, `opportunities/page.tsx`, `keywords/page.tsx`: rewrote to use api.ts functions (which have correct URL handling) instead of raw `fetch()`
- All 5 client components: added `Array.isArray(x) ? x : []` guards in useState initializers
- `IdeasClient.tsx`: `(idea.reasoning?.length ?? 0) > 0`, `(idea.reasoning ?? []).map(...)`, `(idea.related_app_ids?.length ?? 0) > 0`
- `NicheRadarClient.tsx`: `Array.isArray(data?.niches) ? data.niches : []`, `(niche.keywords ?? []).slice(0, 3)`, `data?.scanned_at ?? null`
- Created `frontend/src/components/ErrorBoundary.tsx` — React class component with `getDerivedStateFromError`, "Something went wrong" fallback with AlertTriangle icon and "Try again" button
- Wrapped all 5 broken client components with `<ErrorBoundary>`

**Files Modified:**
- `frontend/src/lib/api.ts` — `_resolveApiBase()` server/client context detection
- `frontend/src/app/trending/page.tsx` — use api.ts functions
- `frontend/src/app/opportunities/page.tsx` — use api.ts functions
- `frontend/src/app/keywords/page.tsx` — use api.ts functions
- `frontend/src/app/trending/TrendingClient.tsx` — Array.isArray guard + ErrorBoundary
- `frontend/src/app/opportunities/OpportunitiesClient.tsx` — Array.isArray guard + ErrorBoundary
- `frontend/src/app/keywords/KeywordsClient.tsx` — Array.isArray guards + ErrorBoundary
- `frontend/src/app/ideas/IdeasClient.tsx` — null-safe reasoning/related_app_ids + ErrorBoundary
- `frontend/src/app/niche-radar/NicheRadarClient.tsx` — null-safe niches/keywords + ErrorBoundary

**Files Created:**
- `frontend/src/components/ErrorBoundary.tsx` — React error boundary component

**Key Gotchas:**
- `BACKEND_URL` (no `NEXT_PUBLIC_` prefix) is used only in server context (Node); `NEXT_PUBLIC_API_URL` is baked into the browser bundle at build time
- When `.catch(() => [])` wraps a `fetch()` that returns valid JSON (like a 404 with `{"detail":"Not Found"}`), the catch never fires — the response must check `r.ok` before calling `.json()`
- All client components must defensively guard array props; server-side fetch failures silently produce error objects that look truthy but are not arrays

---

## Session: 2026-03-09 (Session 11 — Large-Scale Discovery Engine)

**Summary:** Removed all app caps, built a perpetual large-scale discovery engine covering all App Store categories × 20 countries × 3 chart types + 100+ keyword searches + developer expansion.

**Limits Removed:**
- `cap = settings.max_test_apps` guard removed from all 4 ScraperWorker methods
- `if cap: apps = apps[:cap]` slicing removed from `scrape_quick_refresh_all` + `scrape_all_tracked_apps`
- `if cap and ... >= cap: continue/break` guards removed from `scrape_search_results` + `scrape_top_charts`
- `from app.config import settings` import removed from tasks.py (no longer needed)
- Search limit raised: 50 → 200 (appstore.py `get_search_results`)
- Chart limit raised: 100 → 200 (appstore.py `get_top_charts`)

**New Models:**
- `DiscoveryQueue` — persistent queue of app IDs awaiting full scrape (status: pending/scraping/done/failed, priority, source, failed_attempts, added_at, processed_at)
- `DiscoveryProgress` — tracks which chart/keyword/developer source was last scanned (prevents re-fetching same source multiple times per day)

**New File: `backend/app/workers/discovery_engine.py`**
- `DiscoveryEngine` class with 4 discovery methods:
  - `run_chart_discovery_batch(batch_size)` — all 21 genres × 20 countries × 3 chart types; processes `batch_size` slots per call, resumable via DiscoveryProgress
  - `run_keyword_discovery()` — 100+ keywords via iTunes Search API (200 results each)
  - `run_developer_expansion(limit)` — all apps by each known developer via iTunes artist lookup
  - `process_queue(batch_size)` — drains discovery_queue with full scrape; priority: higher priority first, then FIFO
  - `get_metrics()` — live counts: total_apps, new_today, queue_pending/done/failed, sources_scanned, coverage_pct

**New Scheduler Jobs (4 added):**
- `discovery_keywords` — every 6h, first run +2min
- `discovery_charts` — every 2h, first run +5min
- `discovery_developer` — every 12h, first run +10min
- `queue_processor` — every 30min, first run +15min

**Total scheduler jobs:** was 5, now 8

**New API Endpoints (4 added):**
- `GET /api/v1/admin/discovery/metrics`
- `POST /api/v1/admin/discovery/run-charts?batch_size=20`
- `POST /api/v1/admin/discovery/run-keywords`
- `POST /api/v1/admin/discovery/process-queue?batch_size=25`

**Discovery Coverage (theoretical maximum per day):**
- Charts: 3 × 21 × 20 = 1,260 unique chart feeds × 200 apps = 252,000 app IDs/day
- Keywords: 100+ × 200 results = 20,000 app IDs/day
- Total unique after dedup: ~50,000–100,000 new IDs/day → queue grows continuously

**Key Design Decisions:**
- `enqueue()` does single-query dedup vs both `apps` and `discovery_queue` tables
- `_ran_today()` prevents re-scanning same source within a day
- Keyword hits get priority=2 (higher than chart hits priority=1) — search results are more intent-aligned
- `failed_attempts < 3` retry logic; after 3 failures status → "failed" (skipped)
- `run_scrape_task()` (bootstrap) now also calls discovery engine + processes 50 from queue

**Files Modified:**
- `backend/app/models/models.py` — DiscoveryQueue + DiscoveryProgress models
- `backend/app/workers/tasks.py` — all caps removed, settings import removed, run_scrape_task expanded
- `backend/app/workers/scheduler.py` — 4 new jobs, updated docstring
- `backend/app/scrapers/appstore.py` — limits raised to 200
- `backend/app/api/routes.py` — 4 new admin/discovery endpoints
- `backend/DEPLOYMENT.md` — Discovery Engine section added

**Files Created:**
- `backend/app/workers/discovery_engine.py`

**Bootstrap instructions for Railway:**
1. Open `https://your-backend.railway.app/docs`
2. `POST /api/v1/admin/bootstrap` → click Execute
3. Poll `GET /api/v1/admin/bootstrap/status` every minute to track progress
4. When `total_apps > 0`, refresh the dashboard

**Key Gotcha:** Bootstrap is idempotent — calling it twice while running returns 409. Calling it on a non-empty DB is safe (scrape/upsert logic skips existing records).

---
