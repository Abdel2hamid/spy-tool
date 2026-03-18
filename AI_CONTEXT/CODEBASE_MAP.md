# Codebase Map

Complete map of every important file and directory.

---

## Root Structure

```
appstore-spy-tool/
├── backend/                    Python FastAPI backend
├── frontend/                   Next.js 14 frontend
├── AI_CONTEXT/                 This folder — AI session memory + documentation
└── PRODUCT_STRATEGY_REPORT.md  Strategic analysis document
```

---

## Backend Structure

```
backend/
├── app/
│   ├── main.py                 FastAPI app entry point, lifespan, _MIGRATIONS list (~40 SQL statements)
│   ├── config.py               Pydantic Settings (env vars, DATABASE_URL, GOOGLE_TRENDS_ENABLED, etc.)
│   ├── database/
│   │   └── __init__.py         SQLAlchemy engine (sync), SessionLocal, Base, get_db()
│   ├── api/
│   │   └── routes.py           ALL API endpoints — single file, ~2800 lines, 50+ routes
│   ├── models/
│   │   ├── models.py           All SQLAlchemy ORM models (25+ tables)
│   │   └── schemas.py          All Pydantic request/response schemas
│   ├── scrapers/
│   │   ├── app_details.py      AppStoreAppScraper — iTunes Lookup API + RSS reviews + version HTML
│   │   ├── appstore.py         AppStoreScraper — iTunes Search + iTunes RSS top charts
│   │   └── appstore_search_scraper.py  AppStoreSearchScraper — Playwright keyword rank tracking
│   ├── workers/
│   │   ├── scheduler.py        APScheduler setup; 20+ recurring jobs
│   │   ├── tasks.py            ScraperWorker + ScoringWorker + pipeline wrappers
│   │   └── discovery_engine.py DiscoveryEngine (chart + keyword + developer expansion)
│   ├── jobs/
│   │   └── keyword_rank_tracker.py  KeywordRankTracker (Playwright-based, may not run on Railway)
│   ├── scoring/
│   │   ├── engine.py           ScoringEngine — all scoring formulas (trending, opportunities, weakness)
│   │   ├── feature_gaps.py     FeatureGapAnalyzer — NLP pattern matching on negative reviews
│   │   ├── idea_generator.py   IdeaGenerator — 3 patterns → AppIdea records
│   │   ├── ai_potential.py     AI integration potential scoring
│   │   └── weights.py          Scoring weight constants
│   ├── config/
│   │   ├── scoring_config.py   Central config for all scoring thresholds + algorithm params
│   │   ├── rank_curves.py      Category-aware rank → daily download bands (8 bands × 9 categories)
│   │   ├── category_arpu_profiles.py  Revenue ARPU profiles per category (subscription/IAP/ad)
│   │   └── calibration_profiles.py   Per-category calibration multipliers for download estimation
│   ├── services/               35 service modules (see list below)
│   └── utils/                  Utility modules
├── tests/
│   ├── test_import_search.py   36 tests for AppImportService
│   ├── test_download_estimator.py  70 tests for DownloadEstimator + ConfidenceEngine
│   ├── test_growth_intelligence.py 41 tests for AdIntelligence + CampaignTracking
│   └── ...
├── requirements.txt
└── venv/
```

---

## All Service Files (`backend/app/services/`)

| File | Class / Purpose |
|---|---|
| `app_import_service.py` | `AppImportService` — on-demand search + import (lookup_app writes to DB; search_apps is read-only) |
| `download_estimator.py` | `DownloadEstimator` — 4-layer ensemble (rank curve / review velocity / keyword visibility / momentum) |
| `confidence_engine.py` | `ConfidenceEngine` — Bayesian confidence from 5 multiplicative factors |
| `revenue_estimator.py` | `RevenueEstimator` — ARPU-based revenue estimation per category |
| `install_estimator.py` | `InstallEstimator` — legacy L1-only estimator (kept for backward compat) |
| `metric_snapshot_service.py` | `MetricSnapshotService` — writes `app_metric_snapshots` on each scoring cycle |
| `trending_compute_service.py` | `TrendingComputeService` — precomputes `app_trending_scores` every 10 min |
| `blowing_up_service.py` | `BlowingUpService` — precomputes `app_blowing_up_scores` every 15 min |
| `ad_intelligence_service.py` | `AdIntelligenceService` — Apple Search Ads heuristic + optional Meta Ads |
| `campaign_tracking_service.py` | `CampaignTrackingService` — classifies growth events (paid_push, organic_breakout, etc.) |
| `keyword_intelligence_pipeline.py` | `KeywordIntelligencePipeline` — Google Trends + Apple signals + opportunity scoring |
| `keyword_quality_engine.py` | `KeywordQualityEngine` — quality_score + quality_tier (A/B/C) + canonical dedup |
| `keyword_extraction_service.py` | `KeywordExtractionService` — extracts keywords from app title/subtitle/description |
| `keyword_discovery_service.py` | `KeywordDiscoveryService` — autocomplete + prefix/suffix expansion per app |
| `keyword_discovery_engine.py` | `KeywordDiscoveryEngine` — 3-phase global discovery (alphabet + MZSearchHints + n-gram) |
| `keyword_intelligence.py` | `KeywordIntelligenceService` — per-app keyword scoring from search snapshots |
| `keyword_history.py` | `KeywordHistoryService` — rank-over-time from `keyword_search_snapshots` |
| `keyword_search_service.py` | Keyword search helpers |
| `keyword_trends_service.py` | `fetch_trend_score(keyword)` via pytrends |
| `keyword_gap_service.py` | `KeywordGapService` — gap analysis vs. competitors |
| `alphabet_mining_service.py` | `AlphabetMiningService` — A-Z prefix expansion for keyword discovery |
| `competitor_keyword_service.py` | `CompetitorKeywordService` — mines competitor apps' keywords |
| `opportunity_service.py` | `OpportunityService` — keyword opportunity scoring |
| `apple_autocomplete_service.py` | `fetch_autocomplete(keyword)` — Apple MZSearchHints API |
| `global_keyword_sink.py` | `GlobalKeywordSink` — unified keyword ingestion + dedup |
| `niche_radar.py` | `NicheRadarEngine` — 3-pass niche discovery |
| `review_intelligence.py` | `ReviewIntelligenceService` — Claude Haiku LLM review batch analysis |
| `review_scraper_service.py` | `ReviewScraperService` — deep review scraping (500 reviews per app) |
| `review_sentiment_service.py` | `ReviewSentimentService` — rule-based sentiment tagging |
| `feature_gap_service.py` | Feature gap helpers |
| `app_autopsy.py` | `AppAutopsyService` — "why is this app winning" narrative |
| `backfill_keyword_structure.py` | One-time backfill utility |
| `keyword_quality_backfill.py` | Quality score backfill utility |

---

## Frontend Structure

```
frontend/src/
├── app/                          Next.js App Router pages (17 routes)
│   ├── layout.tsx                Root layout — Providers wrapper
│   ├── page.tsx                  / — Dashboard home
│   ├── apps/
│   │   ├── page.tsx              /apps — App catalog
│   │   ├── AppsClient.tsx        Client: filter/sort/paginate app list
│   │   └── [id]/
│   │       └── page.tsx          /apps/[id] — 9-tab app detail page
│   ├── trending/
│   │   ├── page.tsx
│   │   └── TrendingClient.tsx
│   ├── blowing-up/
│   │   ├── page.tsx
│   │   └── BlowingUpClient.tsx   Reference design for new pages
│   ├── latest-apps/
│   │   ├── page.tsx
│   │   └── LatestAppsClient.tsx
│   ├── keywords/
│   │   ├── page.tsx
│   │   └── KeywordsClient.tsx
│   ├── opportunities/
│   │   ├── page.tsx
│   │   └── OpportunitiesClient.tsx
│   ├── niche-radar/
│   │   ├── page.tsx
│   │   └── NicheRadarClient.tsx
│   ├── ideas/
│   │   ├── page.tsx
│   │   └── IdeasClient.tsx
│   ├── campaigns/
│   │   ├── page.tsx
│   │   └── CampaignsClient.tsx
│   ├── ads/
│   │   ├── page.tsx
│   │   └── AdsClient.tsx
│   ├── discover/
│   │   └── page.tsx              Redirects to /apps
│   ├── rankings/
│   │   └── page.tsx
│   ├── competitors/
│   │   └── page.tsx              UI stub — no backend
│   ├── alerts/
│   │   └── page.tsx              UI stub — no backend
│   └── settings/
│       └── page.tsx              UI stub — no backend
├── components/
│   ├── AppShell.tsx              REQUIRED wrapper for all pages (Sidebar + Header)
│   ├── Sidebar.tsx               Left nav with all page links
│   ├── Header.tsx                Top bar: global search + notifications + theme toggle
│   ├── Charts.tsx                Recharts wrappers
│   ├── StatsCard.tsx             KPI card with trend indicator
│   ├── TrendingAppCard.tsx       Trending app card
│   ├── OpportunityOfDayCard.tsx  Featured opportunity card
│   ├── KeywordOpportunityCard.tsx
│   ├── RankHistoryChart.tsx      Standalone rank chart
│   ├── ThemeToggle.tsx           Dark/light mode toggle
│   ├── Providers.tsx             Theme provider
│   ├── ErrorBoundary.tsx         Client-side error boundary
│   └── index.ts                  Barrel exports
└── lib/
    ├── api.ts                    Typed API client (~1500 lines): all types + fetch functions
    ├── estimate-format.ts        fmtNum(), fmtRev(), fmtRange(), confidenceLabel()
    └── utils.ts                  cn() Tailwind class merger
```

---

## Top 12 Most Critical Files

| Priority | File | Why Critical |
|---|---|---|
| 1 | `backend/app/api/routes.py` | All API logic — 2800 lines, 50+ endpoints |
| 2 | `backend/app/models/models.py` | All database schema — 25 ORM models |
| 3 | `backend/app/main.py` | App startup + _MIGRATIONS list (schema evolution) |
| 4 | `frontend/src/lib/api.ts` | All TypeScript types + every API call |
| 5 | `backend/app/services/download_estimator.py` | 4-layer estimation — core intelligence engine |
| 6 | `backend/app/scoring/engine.py` | Trending + opportunity scoring |
| 7 | `backend/app/workers/tasks.py` | ScraperWorker + ScoringWorker pipeline |
| 8 | `backend/app/workers/scheduler.py` | 20+ scheduled jobs |
| 9 | `frontend/src/components/Header.tsx` | Global search — App Store URL/ID import |
| 10 | `backend/app/services/app_import_service.py` | On-demand app search + import |
| 11 | `frontend/src/app/apps/[id]/page.tsx` | 9-tab app detail page (main UX surface) |
| 12 | `backend/app/models/schemas.py` | All Pydantic schemas for API contracts |

---

## Patterns

### Adding a new API endpoint
1. Add route in `backend/app/api/routes.py`
2. Add Pydantic schema in `backend/app/models/schemas.py`
3. Add TypeScript type + fetch function in `frontend/src/lib/api.ts`

### Adding a new DB table
1. Add model class in `backend/app/models/models.py`
2. Add migration SQL to `_MIGRATIONS` list in `backend/app/main.py`
3. Restart backend — migrations run automatically on startup

### Adding a new page
1. Create `frontend/src/app/{route}/page.tsx` (thin server component)
2. Create `frontend/src/app/{route}/{Name}Client.tsx` with `'use client'`
3. Wrap content in `<AppShell>` (provides sidebar + header)
4. Add nav item in `frontend/src/components/Sidebar.tsx`

### Adding a new service
1. Create `backend/app/services/{name}_service.py`
2. Register in `backend/app/workers/tasks.py` if it's part of the scoring pipeline
3. Add scheduler job in `backend/app/workers/scheduler.py` if it needs periodic runs

---

*Documentation generated by auditing the current codebase. Last updated: 2026-03-18.*
