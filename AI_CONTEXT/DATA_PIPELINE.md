# Data Pipeline

How data flows from Apple's servers through the system to the frontend.

---

## Complete Data Flow Overview

```
Apple APIs / App Store Pages
         │
         ▼
    [SCRAPERS]  ──── pull raw data ────
         │
         ▼
    [WORKERS]  ──── parse + write to DB ────
         │
         ▼
  [POSTGRESQL]  ──── persisted data ────
         │
         ▼
  [SCORING/NLP]  ──── analytics computed, written back to DB ────
         │
         ▼
  [FASTAPI REST API]  ──── reads DB, returns JSON ────
         │
         ▼
  [NEXT.JS FRONTEND]  ──── fetches on client, renders ────
```

---

## Phase 1: Data Ingestion (Scraping)

### Pipeline A — App Discovery (every 12h)

```
job_discovery (scheduler)
    └── ScraperWorker.scrape_search_results(keywords)
            └── AppStoreScraper.get_search_results(keyword)
                    └── iTunes Search API
                            └── create/update: App, Keyword, AppKeyword rows
    └── ScraperWorker.scrape_top_charts()
            └── AppStoreScraper.get_top_charts()
                    └── iTunes RSS JSON feeds
                            └── create/update: App, Category, Ranking rows
```

### Pipeline B — Full Metadata Refresh (every 6h)

```
job_full_metadata (scheduler)
    └── ScraperWorker.scrape_all_tracked_apps()
            └── for each App in DB:
                    └── AppStoreAppScraper.scrape_full_app_data(app_id)
                            ├── iTunes Lookup API → update App row
                            ├── App Store HTML scrape → upsert AppVersion rows
                            └── iTunes RSS Reviews → insert new Review rows (dedup by review_id)
    └── ScraperWorker.scrape_top_charts()  ← also refreshes rankings
```

### Pipeline C — Hourly Quick Refresh (every 1h)

```
job_hourly_reviews_ratings (scheduler)
    └── ScraperWorker.scrape_quick_refresh_all()
            └── for each App in DB:
                    ├── iTunes Lookup API → update rating + review count + current_version
                    └── iTunes RSS Reviews → insert new reviews (NO version HTML scraping)
```

### Pipeline D — Keyword Rank Tracking (every 6h)

```
job_keyword_rank_tracker (scheduler)
    └── run_keyword_rank_tracker()
            └── KeywordRankTracker.run()
                    └── AppStoreSearchScraper.search_many(keywords)
                            └── Playwright: apps.apple.com/us/search?q={term}
                                    └── _EXTRACT_JS → raw results
                                    └── iTunes Lookup batch → icon URLs
                    └── _save_snapshots() → insert KeywordSearchSnapshot rows
                    └── _update_app_keyword_positions() → update AppKeyword.position
```

---

## Phase 2: Analytics Processing (Scoring)

Triggered every hour by `job_hourly_scoring`, runs in a thread pool executor.

```
ScoringWorker.update_opportunities()
    │
    ├── 1. Clean stale keywords (no app links)
    │
    ├── 2. Update keyword metrics
    │       └── ScoringEngine.update_keyword_metrics()
    │               search_volume = app_count × 850  (proxy estimate)
    │               difficulty = min(app_count, 60)
    │               trend = TREND_MAP lookup
    │
    ├── 3. Score opportunities
    │       └── for each (App, primary Keyword) pair:
    │               ScoringEngine.score_opportunity()
    │               └── writes/updates Opportunity row
    │
    ├── 4. Compute market weakness
    │       └── for each App with reviews:
    │               ScoringEngine.compute_market_weakness(app_id)
    │               └── writes/updates AppMarketWeakness rows (per country)
    │
    ├── 5. Compute feature gaps
    │       └── for each App with negative reviews:
    │               FeatureGapAnalyzer.compute_for_app(app_id)
    │               └── deletes old FeatureGap rows, inserts fresh ones
    │
    └── 6. Generate AI ideas
            └── IdeaGenerator.generate_all()
                    ├── _ideas_from_feature_gaps() → Pattern A ideas
                    ├── _ideas_from_weak_markets() → Pattern B ideas
                    └── _ideas_from_keywords() → Pattern C ideas
                    └── _save_ideas() → upsert AppIdea rows

ScoringWorker.generate_daily_report()
    └── ScoringEngine.get_top_trending_apps()
    └── ScoringEngine.generate_opportunity_of_day()
    └── writes/updates DailyReport row (keyed by date)
```

---

## Phase 3: API Delivery

FastAPI routes read from PostgreSQL using SQLAlchemy ORM queries.

**Request flow:**
```
Frontend fetch() → FastAPI route → get_db() dependency → SQLAlchemy query → response_model serialization → JSON response
```

**Key query patterns:**
- Filtering: `db.query(App).filter(...)` with composable `and_()` conditions
- Pagination: `.offset(skip).limit(limit)`
- Ordering: `_VALID_SORT_FIELDS[sort_by]` dict lookup prevents SQL injection on sort fields
- Computed on-demand: Market weakness and feature gaps can be computed at request time if DB is empty

**Caching:**
- `DailyReport` table caches the daily dashboard data (opportunity of day, trending apps)
- No in-memory cache; all queries hit PostgreSQL directly
- Frontend uses `cache: 'no-store'` on all fetches

---

## Phase 4: Frontend Display

**Data fetching pattern (all pages):**
```
page.tsx (server component, thin wrapper)
    └── *Client.tsx ('use client')
            └── useEffect(() => { fetchData() }, [])
                    └── api.ts function → fetch() to /api/v1/...
                            └── useState to store results
                            └── JSX renders with loaded data
```

**Loading states:**
- All client components show skeleton/loading states while fetching
- Error states show simplified fallback UI

**Dark mode:**
- Managed by `ThemeToggle` component + `next-themes` provider
- All Tailwind classes use `dark:` variants

---

## Data Freshness Summary

| Data Type | Update Frequency | Source |
|-----------|-----------------|--------|
| App metadata (name, rating, version) | Hourly (quick) + 6h (full) | iTunes Lookup API |
| Reviews | Hourly | iTunes RSS API |
| Version history | Every 6h | App Store HTML |
| Chart rankings | Every 6h + 12h | iTunes RSS JSON |
| Opportunity scores | Hourly | Computed from DB |
| Market weakness | Hourly | Computed from reviews |
| Feature gaps | Hourly | NLP on reviews |
| AI ideas | Hourly | Computed from signals |
| Keyword snapshots | Every 6h | Playwright scrape |
| Keyword intelligence | On-demand (from snapshots) | Computed from snapshots |
| Daily report | Hourly | Computed summary |

---

## Database Write Patterns

| Pattern | Used For | Code |
|---------|----------|------|
| `db.merge()` | Update-or-insert by PK | App metadata updates |
| Filter + update existing or create new | Reviews, versions | Check `review_id` uniqueness |
| PostgreSQL `ON CONFLICT DO UPDATE` | AI ideas (upsert by title) | `idea_generator.py:_save_ideas()` |
| Delete + bulk insert | Feature gaps (full recompute) | `feature_gaps.py:compute_for_app()` |
| `db.add()` | New records | Snapshots, new apps |
