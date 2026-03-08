# Architecture Overview

## High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                │
│   iTunes Lookup API  │  iTunes RSS API  │  App Store HTML/JS pages  │
└──────────┬──────────────────┬──────────────────┬────────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SCRAPERS LAYER                              │
│   AppStoreScraper     AppStoreAppScraper    AppStoreSearchScraper   │
│  (iTunes search +    (metadata + reviews   (Playwright browser —   │
│   top charts RSS)     + version history)    live search results)   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ raw data dicts
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         WORKERS LAYER                               │
│   ScraperWorker (async)           ScoringWorker (sync, thread pool) │
│   • scrape_search_results()       • update_opportunities()          │
│   • scrape_top_charts()           • compute_market_weakness()       │
│   • scrape_app_full_details()     • compute_feature_gaps()          │
│   • scrape_quick_refresh_all()    • generate_ideas()                │
│   • scrape_all_tracked_apps()     • generate_daily_report()         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ SQLAlchemy ORM writes
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       POSTGRESQL DATABASE                           │
│   14 tables: apps, rankings, reviews, keywords, app_analytics,     │
│   app_market_weakness, feature_gaps, keyword_search_snapshots,     │
│   app_ideas, opportunities, app_versions, app_keywords, categories, │
│   daily_reports                                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ SQLAlchemy ORM reads
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FASTAPI REST API  (:8000)                        │
│   /api/v1/*  — 30+ endpoints, all prefixed /api/v1                 │
│   Pydantic response models, CORS enabled                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP/JSON fetch (no-cache)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  NEXT.JS 14 FRONTEND  (:3000)                       │
│   8 pages: Dashboard, Apps, Trending, Opportunities, AI Ideas,      │
│   Keywords, Rankings, Settings                                      │
│   Client-side data fetching, Recharts, Tailwind, dark mode         │
└─────────────────────────────────────────────────────────────────────┘

SCHEDULER (APScheduler AsyncIOScheduler — runs inside FastAPI process)
  hourly_reviews_ratings  → every 1h   (+1h first run)
  hourly_scoring          → every 1h   (+65min first run)
  full_metadata           → every 6h   (+6h first run)
  discovery               → every 12h  (+12h first run)
  keyword_rank_tracker    → every 6h   (+30min first run)
```

---

## Backend Architecture

**Framework:** FastAPI with a synchronous SQLAlchemy session (not async ORM — important for compatibility).

**Entry point:** `backend/app/main.py`
- Defines a `lifespan` context manager that: creates DB tables, starts the APScheduler, then yields
- FastAPI app instance with CORS middleware (all origins allowed for development)
- Single router mounted at `/api/v1`

**Configuration:** `backend/app/config.py`
- Pydantic `Settings` class reads from `.env` file
- Key settings: `DATABASE_URL`, `MAX_TEST_APPS` (0 = no cap, N = limit scraped apps for testing)

**Database session:** `backend/app/database/__init__.py`
- `SessionLocal` factory for synchronous sessions
- `engine` created from `DATABASE_URL`
- `Base` — declarative base for all models
- `get_db()` — FastAPI dependency that yields a session and closes it on exit

**Dependency injection:** Every route function receives `db: Session = Depends(get_db)`.

---

## Scraper Architecture

Three independent scraper classes, each targeting a different data source:

1. **`AppStoreScraper`** — iTunes APIs only (no browser). Fast, reliable. Used for discovery.
2. **`AppStoreAppScraper`** — iTunes APIs + App Store HTML. Used for per-app full data refresh.
3. **`AppStoreSearchScraper`** — Playwright Chromium browser. Used for live keyword rank tracking with sponsored detection.

Scrapers are stateless — they return Python dicts, not ORM objects. Workers translate scraper output into DB writes.

---

## Analytics Architecture

Located in `backend/app/scoring/`:

- **`engine.py`** — `ScoringEngine` class. All metrics: rank velocity, review growth, rating velocity, keyword competition, category growth, AI potential, success probability, opportunity scoring.
- **`feature_gaps.py`** — `FeatureGapAnalyzer` class. NLP extraction of feature requests from reviews using regex trigger patterns + synonym normalization.
- **`idea_generator.py`** — `IdeaGenerator` class. Synthesizes feature gaps + market weakness + keyword data into scored `AppIdea` records via 3 patterns.
- **`weights.py`** — Scoring weight constants, category multipliers, difficulty/trend thresholds.

Analytics run synchronously in a thread-pool executor (via `asyncio.to_thread`) so they don't block the event loop.

---

## Frontend Architecture

**Framework:** Next.js 14 App Router.

**Pattern:** Each page has two files:
- `page.tsx` — Thin server component (metadata, imports client component)
- `*Client.tsx` — Client component (`'use client'`) that handles all data fetching with `useEffect` + `useState`

This means **all data fetching is client-side** (no server-side `fetch` at build time) using `no-cache` requests to the FastAPI backend.

**API layer:** `frontend/src/lib/api.ts` — Single file with all TypeScript interfaces and `fetch` wrapper functions. Base URL: `process.env.NEXT_PUBLIC_API_URL || '/api/v1'`.

**Layout:** `AppShell` component wraps every page. It renders `Sidebar` + `Header` + content area. Pages that do NOT use `AppShell` will appear unstyled (white background, no nav).

**Routing (8 pages):**
```
/              → Dashboard
/apps          → App Browser (filtered list)
/apps/[id]     → App Detail (8 tabs)
/trending      → Trending Apps
/opportunities → Keyword Opportunities
/ideas         → AI-Generated App Ideas
/keywords      → Keyword Intelligence
/rankings      → Chart Rankings
/settings      → Settings (UI only)
```

---

## Scheduler Architecture

`backend/app/workers/scheduler.py` — Module-level `AsyncIOScheduler` singleton.

`setup_scheduler()` must be called before `scheduler.start()`. Called in `main.py` lifespan.

All jobs use `max_instances=1` (no concurrent runs of same job), `coalesce=True` (merge missed fires), `misfire_grace_time=300s` (allow 5-minute late start).

Jobs are async functions that instantiate workers internally and call cleanup in `finally` blocks.
