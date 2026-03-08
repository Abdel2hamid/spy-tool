# Codebase Map

Complete map of every important file and directory.

---

## Root Structure

```
appstore-spy-tool/
├── backend/                    Python FastAPI backend
├── frontend/                   Next.js 14 frontend
├── AI_CONTEXT/                 This folder — AI session memory
├── PRODUCT_STRATEGY_REPORT.md  Strategic analysis document
└── README.md                   (if present)
```

---

## Backend Structure

```
backend/
├── app/
│   ├── main.py                 FastAPI app entry point, lifespan, startup
│   ├── config.py               Pydantic Settings (env vars, DATABASE_URL, MAX_TEST_APPS)
│   ├── database/
│   │   └── __init__.py         SQLAlchemy engine, SessionLocal, Base, get_db()
│   ├── api/
│   │   ├── __init__.py         Imports router
│   │   └── routes.py           ALL 30+ API endpoints (single file, ~1050 lines)
│   ├── models/
│   │   ├── models.py           SQLAlchemy ORM models (14 tables)
│   │   └── schemas.py          Pydantic request/response schemas
│   ├── scrapers/
│   │   ├── appstore.py         AppStoreScraper — iTunes search + top charts RSS
│   │   ├── app_details.py      AppStoreAppScraper — metadata + versions + reviews
│   │   ├── appstore_search_scraper.py  AppStoreSearchScraper — Playwright live search
│   │   └── appstore_backup.py  Legacy backup (not actively used)
│   ├── workers/
│   │   ├── tasks.py            ScraperWorker + ScoringWorker + pipeline functions
│   │   └── scheduler.py        APScheduler setup, 5 recurring job definitions
│   ├── jobs/
│   │   └── keyword_rank_tracker.py  KeywordRankTracker class + standalone runner
│   ├── scoring/
│   │   ├── engine.py           ScoringEngine — all metrics and scoring formulas
│   │   ├── feature_gaps.py     FeatureGapAnalyzer — NLP review mining
│   │   ├── idea_generator.py   IdeaGenerator — 3-pattern idea synthesis
│   │   └── weights.py          Scoring weight constants and multipliers
│   └── services/
│       └── keyword_intelligence.py  KeywordIntelligenceService — per-app keyword scoring
├── alembic/                    Database migration config (not actively used — app uses create_all)
├── requirements.txt            Python dependencies
└── venv/                       Python virtual environment
```

---

## File-Level Details — Backend

### `app/main.py`
- Creates `FastAPI` app with CORS (all origins allowed)
- `lifespan` context manager: creates DB tables → calls `setup_scheduler()` → `scheduler.start()` → yields → `scheduler.shutdown(wait=False)`
- Mounts `router` at `/api/v1`
- **Note:** Startup scrape is commented out. All data collection happens via the scheduler.

### `app/config.py`
- `Settings` class inherits `pydantic_settings.BaseSettings`
- Reads from `.env` file in backend root
- Key vars: `DATABASE_URL`, `MAX_TEST_APPS` (0 = no cap)
- `settings` singleton imported everywhere

### `app/database/__init__.py`
- `engine = create_engine(settings.database_url)` (sync engine, not async)
- `SessionLocal = sessionmaker(bind=engine)`
- `Base = declarative_base()`
- `get_db()` — FastAPI dependency generator

### `app/api/routes.py`
- Single `APIRouter` with prefix=`""` (mounted at `/api/v1` in main.py)
- ~1050 lines, all routes in one file
- Groups: Dashboard, Apps, Discovery/Trending, Keywords, Rankings, Categories, Ideas, Scraping, Scheduler, Keyword Tracker
- Uses `Depends(get_db)` for all DB access
- Important: `_VALID_SORT_FIELDS` dict at line ~57 maps sort_by strings to SQLAlchemy columns

### `app/models/models.py`
- 14 SQLAlchemy model classes
- All inherit from `Base`
- Uses `func.now()` for server-side default timestamps
- JSON columns for flexible data (screenshots, signals, reasoning, IAP data)
- See `DATABASE_SCHEMA.md` for full details

### `app/models/schemas.py`
- Pydantic v2 schemas with `model_config = ConfigDict(from_attributes=True)`
- Input schemas: `*Create`, `*Update`
- Output schemas: `*Response`
- All list response wrappers: `AppListResponse`, `AppIdeaListResponse`, `KeywordSnapshotListResponse`

### `app/scrapers/appstore.py`
- `AppStoreScraper` class
- `get_search_results(keyword, limit=20, country="us")` → list of app dicts
- `get_top_charts(chart_type, category, limit=200)` → list of ranking dicts
- `_GENRE_IDS` dict: 21 category slugs → Apple genre IDs
- Uses `urllib.request` + `json.loads`

### `app/scrapers/app_details.py`
- `AppStoreAppScraper` class
- `get_app_details(app_id, country="us")` → metadata dict
- `get_app_versions(app_id, country="us")` → list of version dicts (see version history scraping in SCRAPERS_INDEX.md for the fragile JSON extraction)
- `get_app_reviews(app_id, country="us", limit=500)` → list of review dicts
- `scrape_full_app_data(app_id, country="us")` → combined dict
- `_find_key(obj, key, depth)` — recursive JSON tree search (critical helper for version extraction)

### `app/scrapers/appstore_search_scraper.py`
- `AppStoreSearchScraper` class — async context manager
- `search(keyword, country, max_results, retries)` → result dict with positions + sponsored flags
- `search_many(keywords, country, max_results, concurrency)` → list of result dicts
- `_EXTRACT_JS` — inline JavaScript string executed in the Playwright page context
- `_fetch_icons(app_ids, country)` — synchronous iTunes batch lookup for icon URLs
- **URL:** `https://apps.apple.com/{country}/search?q={term}` (NOT `?term=`)
- Called from `KeywordRankTracker` only

### `app/workers/tasks.py`
- `ScraperWorker` (async class):
  - `initialize()` / `cleanup()` — no-op (kept for future Playwright init)
  - `scrape_search_results(keywords)` — discovers apps via iTunes Search
  - `scrape_top_charts(chart_types, categories)` — pulls chart rankings
  - `scrape_app_full_details(app_id_str)` — full single-app refresh
  - `scrape_quick_refresh_all()` — lightweight hourly refresh (metadata + reviews, no version HTML)
  - `scrape_all_tracked_apps()` — full refresh for all apps in DB
- `ScoringWorker` (sync class):
  - `update_opportunities()` — full scoring pipeline: keywords → opportunities → market weakness → feature gaps → ideas
  - `generate_daily_report()` — writes DailyReport record
- `run_scrape_task()` — async pipeline: keyword search → top charts → full details
- `run_scoring_task()` — calls `ScoringWorker` in thread

### `app/workers/scheduler.py`
- Module-level `scheduler = AsyncIOScheduler(timezone="UTC")`
- `setup_scheduler()` — registers all 5 jobs with `IntervalTrigger` and `start_date` offsets
- `_JOB_DEFAULTS` — shared defaults: `max_instances=1, replace_existing=True, coalesce=True, misfire_grace_time=300`
- 5 async job functions: `job_hourly_reviews_ratings`, `job_hourly_scoring`, `job_full_metadata`, `job_discovery`, `job_keyword_rank_tracker`

### `app/jobs/keyword_rank_tracker.py`
- `KeywordRankTracker` class:
  - `run(country, keyword_limit, custom_keywords)` — main entry point
  - `_get_tracked_keywords(limit)` — queries `Keyword.term` ordered by search_volume desc
  - `_save_snapshots(search_data)` — creates `KeywordSearchSnapshot` rows
  - `_update_app_keyword_positions(keyword, results, country)` — upserts `AppKeyword.position`
- `run_keyword_rank_tracker(country, keyword_limit, custom_keywords)` — standalone async function (called by scheduler + API)

### `app/scoring/engine.py`
- `ScoringEngine` class
- Key methods:
  - `calculate_rank_velocity(app_id, days=7)`
  - `calculate_review_growth(app_id, days=30)`
  - `calculate_rating_velocity(app_id, days=30)`
  - `calculate_keyword_competition(keyword)`
  - `calculate_category_growth(category_id, days=30)`
  - `calculate_ai_potential(app_id, name, description)`
  - `calculate_success_probability(...)` — weighted composite
  - `score_opportunity(app_id, primary_keyword)` — full opportunity card
  - `generate_opportunity_of_day()`
  - `get_top_trending_apps(limit)`
  - `get_keyword_opportunities(min_difficulty, max_difficulty)`
  - `update_keyword_metrics()` — derives search_volume and difficulty from app counts
  - `compute_market_weakness(app_id)` — per-country negative review analysis

### `app/scoring/weights.py`
- `SCORING_WEIGHTS` dict: `rank_velocity=0.25, review_growth=0.20, competition=0.20, category_growth=0.15, ai_potential=0.20`
- `CATEGORY_MULTIPLIERS` dict: productivity/business = 1.2x, games = 0.8x
- Threshold dicts for difficulty and trend

### `app/scoring/feature_gaps.py`
- `FeatureGapAnalyzer` class
- `TRIGGER_PATTERNS` list of 18 regex patterns
- `SYNONYM_MAP` dict of 60+ entries for feature normalization
- `compute_for_app(app_id)` — deletes old rows, bulk inserts fresh analysis
- `get_gaps(app_id)` — returns stored gaps sorted by mentions

### `app/scoring/idea_generator.py`
- `IdeaGenerator` class
- `generate_all()` → calls all 3 patterns, saves via upsert, returns count
- `_ideas_from_feature_gaps()`
- `_ideas_from_weak_markets()`
- `_ideas_from_keywords()`
- `_save_ideas(ideas)` → PostgreSQL `insert().on_conflict_do_update(index_elements=["idea_title"])`

### `app/services/keyword_intelligence.py`
- `KeywordIntelligenceService` class
- `get_app_intelligence(app_id_str)` → full intelligence dict
- `get_intelligence_by_db_id(db_id)` → convenience wrapper
- `_compute_intelligence(app, snapshots)` → scoring engine
- `_fallback_from_app_keywords(app)` → uses `AppKeyword` when no snapshots
- `_get_keyword_meta(terms)` → enriches with Keyword table data
- `compute_traffic_sources_all()` → batch traffic mix for all apps

---

## Frontend Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx              Root layout — Providers wrapper
│   │   ├── page.tsx                / route — imports DashboardClient
│   │   ├── DashboardClient.tsx     Dashboard page (all stats, charts, trending)
│   │   ├── apps/
│   │   │   ├── page.tsx            /apps route — imports AppsClient
│   │   │   ├── AppsClient.tsx      App browser with filtering and pagination
│   │   │   └── [id]/
│   │   │       └── page.tsx        /apps/[id] route — 8-tab app detail (~1250 lines)
│   │   ├── trending/
│   │   │   ├── page.tsx
│   │   │   └── TrendingClient.tsx
│   │   ├── opportunities/
│   │   │   ├── page.tsx
│   │   │   └── OpportunitiesClient.tsx
│   │   ├── ideas/
│   │   │   ├── page.tsx
│   │   │   └── IdeasClient.tsx     AI ideas page with score rings, pattern filter
│   │   ├── keywords/
│   │   │   ├── page.tsx
│   │   │   └── KeywordsClient.tsx
│   │   ├── rankings/
│   │   │   └── page.tsx            App selector + rank history chart
│   │   └── settings/
│   │       └── page.tsx            UI-only settings (not wired to backend)
│   ├── components/
│   │   ├── AppShell.tsx            REQUIRED wrapper for all pages (sidebar + header)
│   │   ├── Sidebar.tsx             Left nav — 8 items + mobile slide-in
│   │   ├── Header.tsx              Top bar — search, notifications, theme toggle
│   │   ├── Charts.tsx              SimpleChart + RankHistoryChart (Recharts wrappers)
│   │   ├── StatsCard.tsx           KPI card with trend indicator
│   │   ├── TrendingAppCard.tsx     Card for trending apps list
│   │   ├── OpportunityOfDayCard.tsx  Featured opportunity card
│   │   ├── KeywordOpportunityCard.tsx
│   │   ├── RankHistoryChart.tsx    Standalone rank chart component
│   │   ├── ThemeToggle.tsx         Dark/light mode toggle
│   │   ├── Providers.tsx           Theme provider wrapper
│   │   ├── Navbar.tsx              Alternative nav (not primary)
│   │   └── index.ts                Barrel exports
│   └── lib/
│       ├── api.ts                  ALL TypeScript types + fetch functions (~500 lines)
│       └── utils.ts                cn() Tailwind class merger
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── next.config.js
```

---

## Important Patterns

### Adding a new API endpoint
1. Add route function in `backend/app/api/routes.py`
2. Add Pydantic schema in `backend/app/models/schemas.py`
3. Add TypeScript interface + fetch function in `frontend/src/lib/api.ts`

### Adding a new page
1. Create `frontend/src/app/{route}/page.tsx` (thin server wrapper)
2. Create `frontend/src/app/{route}/{Name}Client.tsx` with `'use client'` directive
3. Wrap content in `<AppShell>` (required for sidebar + header)
4. Add nav item in `frontend/src/components/Sidebar.tsx`

### Adding a new DB table
1. Add model class in `backend/app/models/models.py`
2. Add Pydantic schemas in `backend/app/models/schemas.py`
3. Restart backend — `Base.metadata.create_all()` creates the table automatically

### Adding a new scheduled job
1. Define async function in `backend/app/workers/scheduler.py`
2. Add `scheduler.add_job(...)` call in `setup_scheduler()`
