# Known Limitations

Current technical limitations, workarounds, and risk areas.

---

## Critical Limitations

### 1. No Install or Download Estimates

**Impact:** High — The #1 feature gap vs. all competitors (AppTweak, AppMagic, Sensor Tower).

**What's missing:** There is no estimate of how many times an app has been downloaded (total or per period). Without this, it is impossible to answer "how big is this app?" or "what's the market size?"

**Current workaround:** Review count growth rate is the only available proxy signal for popularity.

**Path to fix:** Build a regression model: `review_velocity × rank_position × category × days_in_top_charts → estimated_installs_range`. Add `estimated_installs_monthly` column to `apps` table.

---

### 2. No Revenue Estimates

**Impact:** High — Revenue is the ultimate market validation signal.

**What's missing:** No estimate of monthly revenue per app or per category.

**Current workaround:** None.

**Path to fix:** `install_estimate × average_revenue_per_install (ARPI)` where ARPI is category-benchmarked. Requires install estimates to be built first.

---

### 3. Keyword Search Volume Is a Rough Estimate

**Impact:** High — Undermines trust in all keyword intelligence features.

**What's missing:** Real Apple keyword search volume data.

**Current implementation:** `search_volume = app_count × 850` (number of apps competing for the keyword × 850). This is a very rough proxy with no empirical basis.

**Path to fix:** Integrate Apple Search Ads API (provides popularity score 0-5) or scrape the Apple Search Ads keyword planner UI via Playwright.

---

### 4. Version History Scraping Is Fragile

**Impact:** Medium — Version history tab can silently break.

**What's missing:** Stable version data extraction.

**Current implementation:** Parses embedded JSON from App Store HTML `<script>` tags using recursive `_find_key()`. The JSON path is `mostRecentVersion → seeAllAction → pageData → shelves[0] → items`.

**Known breakage history:** Apple's `?see-all=versions` URL stopped returning data (now returns 404). CSS class `.version-history__item` no longer exists on current pages.

**Early warning sign:** Version history returns 0 versions for apps that definitely have history.

**Recovery procedure:**
1. Fetch `https://apps.apple.com/us/app/id{app_id}` manually in browser DevTools
2. Search page source for "mostRecentVersion" or "version" in `<script>` tags
3. Update the JSON path in `get_app_versions()` in `app_details.py`

---

### 5. App Store Search Scraping Captures Only ~16 Results

**Impact:** Medium — Cannot track keywords where the app ranks below position 16.

**What's missing:** Deeper pagination (positions 17-100+).

**Current implementation:** Playwright loads one page of search results. Apple loads ~16 results on initial page render.

**Path to fix:** Implement scroll-based pagination or navigate to subsequent result pages. Requires significant Playwright logic updates.

---

### 6. Sponsored Detection Is Heuristic-Based

**Impact:** Medium — May miss some sponsored placements or generate false positives.

**What's missing:** Reliable sponsored detection using Apple's own labeling.

**Current implementation:** Text pattern matching (`/sponsored|search ads|\bAd\b/i`) on card text and CSS attribute inspection. Works for current Apple ad labels but is brittle.

**Risk:** Apple can change ad labeling UI at any time, causing all sponsored placements to appear as organic.

---

### 7. Feature Gap NLP Is Rule-Based

**Impact:** Medium — Misses nuanced feature requests and generates false extractions.

**What's missing:** LLM-quality understanding of review content.

**Current implementation:** 18 regex trigger patterns + 60-entry synonym normalization map.

**Limitations:**
- Cannot understand context (e.g., sarcasm, negation)
- Misses feature requests that don't match trigger patterns
- Normalization map requires manual maintenance as new terms emerge

**Path to fix:** Batch reviews through Claude Haiku or similar for structured feature extraction.

---

### 8. No Historical Data Before Deployment

**Impact:** Medium — All charts and trend analysis only cover time since the tool was first run.

**What's missing:** Historical App Store ranking data.

**Current behavior:** Rank history charts show only data collected since the first scrape. An app that was #1 three months ago shows no history.

**No good fix available:** Historical App Store data requires purchasing from data brokers or enterprise providers.

---

## Moderate Limitations

### 9. iOS Only (No Android / Google Play)

All scraping targets the iOS App Store. No Google Play support.

### 10. US Market Primary Focus

Keyword rank tracking defaults to `country=us`. Multi-country keyword tracking exists in the code (`country` parameter) but the scheduler only runs US. Market weakness analysis does cover multiple countries from review storefront data.

### 11. No Real-Time Alerting

No notification system (email, Slack, webhook) for important events:
- Competitor publishes a new version
- App breaks into top 10 for a keyword
- App drops 50+ ranking positions
- New feature gap detected with high mention count

### 12. iTunes RSS Reviews Are Capped

The iTunes RSS API returns only recent reviews, not the full historical review corpus. Apps with very high review counts (50,000+) will only have the most recent reviews captured.

### 13. Single-Tenant Architecture

The entire codebase is designed for a single operator. No user accounts, no authentication, no per-user data isolation. Cannot be deployed as a multi-tenant SaaS without significant refactoring.

### 14. No API Authentication

All `/api/v1` endpoints are unauthenticated. The backend is intended to be run locally or behind a private network. Do not expose the backend publicly without adding authentication.

### 15. Settings Page Is UI-Only

The `/settings` frontend page has toggles for dark mode, auto-refresh, notifications, and an API key section, but none of these are wired to the backend. They are visual scaffolding only.

### 16. Developer Name Sometimes Shows Subtitle

When scraping App Store search results via Playwright, the "developer" field sometimes extracts the app's subtitle (second line of card text) instead of the actual developer name. This is because the App Store card layout shows subtitle prominently and the scraper's CSS selector fallback picks up subtitle elements.

### 17. `appstore_backup.py` Is Stale

`backend/app/scrapers/appstore_backup.py` is an older version of the scraper kept for reference. It is not imported or used by any active code. It should be deleted to avoid confusion.

---

## Technical Debt

### DB Migrations Not Used

The project includes an `alembic/` directory but migrations are not actively used. All schema changes are applied via `Base.metadata.create_all()` on startup (which only creates new tables, does not alter existing ones). Adding columns to existing tables requires either:
- Manual `ALTER TABLE` SQL in PostgreSQL
- Dropping and recreating tables (data loss)
- Enabling Alembic migrations

### Synchronous SQLAlchemy in Async Context

The ORM uses synchronous SQLAlchemy sessions even though FastAPI and the scrapers are async. The `ScoringWorker` and all route handlers use sync sessions, run in thread pools when called from async context. This works but is not the most efficient pattern for a high-throughput API.

### `MAX_TEST_APPS` Config

`settings.max_test_apps = 0` (no cap). If set to a non-zero value during testing, it limits the number of apps scraped/refreshed. This setting is easy to accidentally leave set, causing incomplete data collection.
