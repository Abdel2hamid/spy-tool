# Features Index

Every implemented feature, how it works, and where it lives in the codebase.

---

## 1. App Discovery

**Status:** ✅ Implemented
**Files:** `backend/app/scrapers/appstore.py`, `backend/app/workers/tasks.py:ScraperWorker.scrape_search_results()`

**How it works:**
- Calls iTunes Search API (`https://itunes.apple.com/search?term={keyword}&entity=software&country=us&limit=20`)
- For each result, creates or updates `App` and `Keyword` and `AppKeyword` records in the DB
- Default discovery keywords: productivity, ai, chat, fitness, finance, education, game, health, travel, music
- Respects `MAX_TEST_APPS` cap from config (0 = no cap)
- Runs automatically every 12 hours via `job_discovery` scheduler job

**Value:** Populates the apps database that all other features depend on.

---

## 2. Top Chart Rankings

**Status:** ✅ Implemented
**Files:** `backend/app/scrapers/appstore.py:AppStoreScraper.get_top_charts()`, `backend/app/workers/tasks.py:ScraperWorker.scrape_top_charts()`

**How it works:**
- Uses iTunes RSS JSON feed: `https://itunes.apple.com/us/rss/{chart}/limit={N}/genre={genre_id}/json`
- Supports 3 chart types: `topfreeapplications`, `toppaidapplications`, `topgrossingapplications`
- Covers 21 genre categories (productivity, games, health-fitness, etc.) mapped to Apple genre IDs
- Creates `Ranking` records with `rank`, `previous_rank`, `rank_velocity`, `chart_type`, `category_id`
- Updates `App.current_rank` for each app seen in charts
- Runs with `full_metadata` (6h) and `discovery` (12h) jobs

**Value:** Enables trending detection, rank history charts, and rank velocity scoring.

---

## 3. App Metadata Scraping

**Status:** ✅ Implemented
**Files:** `backend/app/scrapers/app_details.py:AppStoreAppScraper.get_app_details()`

**How it works:**
- iTunes Lookup API: `https://itunes.apple.com/lookup?id={app_id}&country=us`
- Returns: name, subtitle, description, developer, developer_id, icon_url, screenshots (JSON array), primary/secondary category, is_free, price, currency, in_app_purchases (JSON), current_version, minimum_ios_version, supported_languages, release_date, last_updated, content_rating, current_rating, current_reviews
- Called every 6 hours (full_metadata job) and every 1 hour for quick refresh

---

## 4. Version History Tracking

**Status:** ✅ Implemented
**Files:** `backend/app/scrapers/app_details.py:AppStoreAppScraper.get_app_versions()`

**How it works:**
- Fetches App Store HTML page: `https://apps.apple.com/{country}/app/{name}/id{app_id}`
- Strategy 1 (primary): Parses embedded JSON in `<script>` tag using recursive `_find_key()` to locate `mostRecentVersion` key → navigates to `seeAllAction.pageData.shelves[0].items` for full version list
- Strategy 2 (fallback): Legacy BeautifulSoup CSS selector on `.version-history__item` (may stop working as Apple updates its pages)
- Stores up to 50 versions with: version string, release_date, release_notes, is_latest flag
- Resets all `is_latest=False` before each scrape, then sets the latest version back to True

**Critical note:** Apple uses Svelte-rendered pages. The JSON is embedded in a `<script>` tag — NOT in the HTML DOM. The `?see-all=versions` URL no longer works (returns 404).

---

## 5. Review Collection

**Status:** ✅ Implemented
**Files:** `backend/app/scrapers/app_details.py:AppStoreAppScraper.get_app_reviews()`

**How it works:**
- iTunes RSS API: `https://itunes.apple.com/{country}/rss/customerreviews/page={n}/id={app_id}/sortby=mostrecent/json`
- Paginates through pages until fewer results are returned
- Deduplicates by `review_id` (Apple's unique review identifier) — no duplicate inserts
- Captures: rating (1-5), title, content, date, app_version, storefront (country code), developer_reply_text, developer_reply_date, helpful_count
- Runs hourly (quick refresh) and every 6h (full refresh)

---

## 6. Rank Velocity & Trending Detection

**Status:** ✅ Implemented
**Files:** `backend/app/scoring/engine.py:ScoringEngine.calculate_rank_velocity()`, `ScoringEngine.get_top_trending_apps()`

**How it works:**
- Queries `Ranking` table for recent entries (default 7 days)
- Computes average rank change per data point: `sum(rank_change) / count`
- Positive velocity = improving (rising) rank; negative = declining
- `get_top_trending_apps()` joins ranking velocity with app info, filtered by `rank_velocity > 0`
- Displayed on `/trending` page and Dashboard

---

## 7. Market Weakness Analysis (Per-Country Negative Review Detection)

**Status:** ✅ Implemented
**Files:** `backend/app/scoring/engine.py:ScoringEngine.compute_market_weakness()`, `backend/app/models/models.py:AppMarketWeakness`

**How it works:**
- Queries all `Review` rows for an app, groups by `storefront` (country code)
- Filters out: null storefronts, countries with fewer than 20 reviews
- Computes per country: `total_reviews`, `negative_reviews` (rating ≤ 2), `average_rating`, `negative_ratio`
- Upserts results to `app_market_weakness` table
- Countries with `negative_ratio ≥ 30%` and `average_rating ≤ 3.5` are flagged as market opportunities
- Also exposed as a filter on `GET /apps` (`weak_market=de`, `min_negative_ratio=0.3`)
- Frontend: 6th tab on app detail page with color-coded table (green < 15%, amber 15-30%, red ≥ 30%)

---

## 8. Feature Gap NLP Mining

**Status:** ✅ Implemented
**Files:** `backend/app/scoring/feature_gaps.py:FeatureGapAnalyzer`

**How it works:**
- Scans reviews with rating ≤ 3 and content length ≥ 20 characters
- Applies 18 regex trigger patterns: "wish it had", "should add", "missing a", "please implement", "would love to see", "can't sync", "no support for", "lacks", etc.
- Extracts the phrase following each trigger match
- Normalizes synonyms to canonical names using a 60+ entry map (e.g., "night mode" → "dark mode", "face id" → "biometric login")
- Deduplicates per-review (one review counts once per feature)
- Filters by length (4-60 chars), removes stop words
- Stores to `feature_gaps` table with `feature_name` and `mentions` count
- Frontend: 7th tab on app detail page; also a filter parameter (`min_feature_gaps=5`) on app browser

---

## 9. Keyword Rank Tracking (Live App Store Search)

**Status:** ✅ Implemented
**Files:** `backend/app/scrapers/appstore_search_scraper.py`, `backend/app/jobs/keyword_rank_tracker.py`

**How it works:**
- Playwright Chromium browser navigates to `https://apps.apple.com/{country}/search?q={term}`
  - **IMPORTANT:** URL uses `?q=` not `?term=` (the old `?term=` URL returns 404)
- Waits for `a[href*="/app/"]` selector (20s timeout)
- Scrolls page to bottom and back to top to trigger lazy-loaded content
- Executes `_EXTRACT_JS` in the browser: extracts app_id from href `/id(\d{6,})/`, app name, developer, sponsored status
- **Sponsored detection:** CSS class inspection + text pattern matching (`/sponsored|search ads|\bAd\b/i`)
- **Icon URLs:** Lazy-loaded images cannot be captured headlessly. After extraction, icon URLs are batch-enriched via iTunes Lookup API
- Saves all results to `keyword_search_snapshots` table
- Updates `AppKeyword.position` for matching tracked apps
- Max 50 keywords per run; max 20 results per keyword; concurrency = 2 parallel pages
- Runs every 6h via `keyword_rank_tracker` scheduler job; also triggerable manually via API

---

## 10. Keyword Intelligence Scoring

**Status:** ✅ Implemented
**Files:** `backend/app/services/keyword_intelligence.py:KeywordIntelligenceService`

**How it works:**
- Queries `keyword_search_snapshots` for an app within the last 30 days (configurable)
- Groups by keyword, computes per-keyword score:
  - Position points: rank 1 = 50pts, 2-3 = 35pts, 4-10 = 20pts, 11+ = 10pts
  - Recency weight: 1.0 for < 24h old, degrades linearly to 0.5 at 7 days
  - Frequency weight: appearances / max_appearances across all keywords
  - Organic bonus: +15 if not sponsored
  - Sponsored penalty: -10 if sponsored
- Final score: `sum(pts × recency) × frequency_weight`
- Outputs: primary_keyword, confidence (0-100), organic_keywords list, ads_keywords list, traffic_mix (organic% vs ads%)
- Falls back to `AppKeyword` data if no snapshots exist yet
- Frontend: 8th tab on app detail page (Keywords tab)

---

## 11. AI App Idea Generator

**Status:** ✅ Implemented
**Files:** `backend/app/scoring/idea_generator.py:IdeaGenerator`

**How it works — 3 patterns:**

**Pattern A — Feature Gap Demand:**
- Queries features mentioned across ≥ 2 apps with ≥ 2 total mentions
- Score = `min(app_count × 10 + total_mentions × 2, 95)`
- Idea: "Build an app that solves the '{feature}' gap"

**Pattern B — Weak Market:**
- Queries `AppMarketWeakness` for `negative_ratio ≥ 0.30` AND `average_rating ≤ 3.5`
- Score = `min(int(negative_ratio × 60 + (5.0 - avg_rating) × 10), 95)`
- Idea: "{Category} App for {Country} Market"

**Pattern C — Keyword Gap:**
- Queries keywords with `difficulty < 60` AND `search_volume ≥ 800`
- Score = `min(int((100 - difficulty) × 0.45 + (volume / 1000) × 15 + trend × 0.4), 95)`
- Idea: '"{keyword}" App — Low Competition Opportunity'

All ideas are PostgreSQL upserted (`ON CONFLICT(idea_title) DO UPDATE`) — deduplication by title.
Integrated at the end of `ScoringWorker.update_opportunities()`, running every hour.
Frontend: `/ideas` page with gradient hero, SVG score rings, pattern filter tabs, idea cards.

---

## 12. Opportunity Scoring

**Status:** ✅ Implemented
**Files:** `backend/app/scoring/engine.py:ScoringEngine.score_opportunity()`, `ScoringEngine.calculate_success_probability()`

**How it works:**
- Combines 5 sub-scores: rank velocity, review growth, competition (inverse difficulty), AI potential, category growth
- Weighted sum with category multipliers (productivity gets 1.2x, games 0.8x)
- Outputs: `success_probability` (0-100), `ai_integration_potential`, `competition_score`, `trend_score`, `recommendation` (text)
- Stored in `opportunities` table per (app, keyword) pair
- "Opportunity of Day" = highest success_probability app, cached in `daily_reports`

---

## 13. Dashboard Analytics

**Status:** ✅ Implemented
**Files:** `backend/app/scoring/engine.py`, `backend/app/workers/tasks.py:ScoringWorker.generate_daily_report()`

**How it works:**
- `generate_daily_report()` runs after each scoring cycle
- Writes to `daily_reports` table (keyed by date): top_trending_apps, opportunity_of_day, category_insights
- Frontend Dashboard fetches: 4 KPI stats, opportunity of day card, keyword trends chart, search volume chart, trending apps list

---

## 14. App Browser with Advanced Filtering

**Status:** ✅ Implemented
**Files:** `backend/app/api/routes.py:get_apps()`, `frontend/src/app/apps/AppsClient.tsx`

**How it works:**
- 19 composable filter parameters on `GET /api/v1/apps`
- Text search across name, subtitle, developer, description (SQLAlchemy `or_`)
- Category, developer, min/max rating, reviews, rank, is_free, has_iap, date ranges
- Market weakness filter: `weak_market=de` (country code), `min_negative_ratio=0.3`
- Feature gap filter: `min_feature_gaps=5`
- AI apps filter: `ai_only=true` (matches AI-related keywords in name/description)
- Sort by: 12 fields (rank, rating, reviews, velocity, growth, updated, etc.)
- Frontend: debounced search (400ms), slide-in filter drawer, active filter chips, paginated card grid

---

## 15. Scheduler Control API

**Status:** ✅ Implemented
**Files:** `backend/app/api/routes.py:get_scheduler_status()`, `trigger_job_now()`

**How it works:**
- `GET /scheduler/status` — returns running state + list of all jobs with next_run_time
- `POST /scheduler/jobs/{job_id}/trigger` — immediately triggers a scheduled job by ID

Valid job IDs: `hourly_reviews_ratings`, `hourly_scoring`, `full_metadata`, `discovery`, `keyword_rank_tracker`
