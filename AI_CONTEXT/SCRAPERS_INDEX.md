# Scrapers Index

Documentation for all scraping modules — what they collect, how they work, and where they can break.

---

## Scraper 1: `AppStoreScraper` (`backend/app/scrapers/appstore.py`)

### Purpose
App discovery via keyword search and top chart rankings. Fast and reliable — uses only iTunes APIs.

### Methods

#### `get_search_results(keyword, limit=20, country="us")`
- **URL:** `https://itunes.apple.com/search?term={keyword}&entity=software&country={country}&limit={limit}`
- **Returns:** List of dicts with `app_id`, `name`, `developer`, `icon_url`, `rating`, `review_count`, `price`, `is_free`, `primary_category`, `current_version`, `release_date`, `description`
- **Auth:** None required
- **Rate limiting:** Apple enforces informal rate limits; no documented threshold

#### `get_top_charts(chart_type="topfreeapplications", category="all", limit=200)`
- **URL:** `https://itunes.apple.com/us/rss/{chart_type}/limit={limit}/genre={genre_id}/json`
- **Chart types:** `topfreeapplications`, `toppaidapplications`, `topgrossingapplications`
- **Returns:** List of dicts with `app_id`, `name`, `developer`, `icon_url`, `rank`, `chart_type`, `category_name`, `genre_id`
- **Genre IDs:** Stored in `_GENRE_IDS` dict. 21 categories mapped. "all" maps to `0` (all categories).
- **Data location in RSS:** `entry[i].id.attributes['im:id']` = App Store ID; `entry[i].category.attributes.label` = category name

### Fragility Risks
- ⚠️ Apple may change the RSS feed JSON schema at any time
- ⚠️ `_GENRE_IDS` mapping may become outdated if Apple reorganizes categories
- ⚠️ iTunes Search API returns limited metadata; `get_app_details()` is needed for full data
- ✅ Low risk overall — iTunes APIs have been stable for many years

---

## Scraper 2: `AppStoreAppScraper` (`backend/app/scrapers/app_details.py`)

### Purpose
Full app metadata, complete version history, and user reviews for a specific app.

### Methods

#### `get_app_details(app_id, country="us")`
- **URL:** `https://itunes.apple.com/lookup?id={app_id}&country={country}&entity=software`
- **Returns:** Full metadata dict including screenshots (array), IAP data (JSON), all dates, categories, ratings
- **Fragility:** Very low — iTunes Lookup API is extremely stable

#### `get_app_versions(app_id, country="us")` — ⚠️ HIGH FRAGILITY
- **Primary URL:** `https://apps.apple.com/{country}/app/id{app_id}` (main app page)
- **Strategy:** Fetches the page HTML and searches for an embedded JSON blob inside a `<script>` tag
- **Critical path:**
  1. Find `<script>` tags containing `"mostRecentVersion"`
  2. Parse the JSON blob with `json.loads()`
  3. Call `_find_key(data, "mostRecentVersion")` — recursive search up to depth 12
  4. Navigate: `mostRecentVersion → seeAllAction → pageData → shelves[0] → items`
  5. Each item: `primarySubtitle` = version string, `secondarySubtitle` = date string, `text` = release notes
- **Date format parsed:** `"Thu Mar 05 2026 10:54:19 GMT+0000 (Coordinated Universal Time)"` or ISO format
- **Fallback:** BeautifulSoup search for `.version-history__item` CSS class (likely broken on modern pages)
- **Why the `?see-all=versions` URL no longer works:** Apple returns 404 on that URL

**Fragility risks:**
- 🔴 HIGH RISK — Apple uses Svelte-rendered pages that change structure frequently
- 🔴 The JSON schema inside `<script>` can change with any Apple site update
- 🔴 The `_find_key()` search is depth-limited (12 levels) — deeper nesting would break it
- ⚠️ CSS fallback (`version-history__item`) is likely broken on current Apple pages
- **Recovery approach:** If versions stop working, search for a new `<script>` tag containing the version data. The JSON structure changes but the data is always present somewhere in the embedded scripts.

#### `get_app_reviews(app_id, country="us", limit=500)`
- **URL:** `https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json`
- **Pagination:** Iterates pages 1-N until fewer than expected results are returned
- **Returns:** List of review dicts with `review_id`, `user_name`, `user_url`, `rating`, `title`, `content`, `date`, `app_version`, `storefront`, `developer_reply_text`, `developer_reply_date`, `helpful_count`
- **Fragility:** Low — RSS feed is stable; max 500 reviews total (not the full review corpus)

#### `scrape_full_app_data(app_id, country="us")`
- Orchestrates all three calls above
- Returns dict: `{"details": {...}, "versions": [...], "reviews": [...]}`

#### `_find_key(obj, key, depth=0)` (module-level helper)
- Recursively searches a nested dict/list for a key
- Depth limit: 12 levels
- Returns `None` if not found at any depth
- **Critical for version extraction** — the JSON structure varies by page

---

## Scraper 3: `AppStoreSearchScraper` (`backend/app/scrapers/appstore_search_scraper.py`)

### Purpose
Live App Store search result scraping with sponsored (Apple Search Ads) detection. Captures real search rankings including paid placements.

### How It Works
1. Playwright launches Chromium in headless mode with anti-detection args
2. Navigates to `https://apps.apple.com/{country}/search?q={term}`
3. Waits up to 20s for `a[href*="/app/"]` selector to appear
4. Scrolls to bottom + back to top (attempt to trigger lazy loading)
5. Executes `_EXTRACT_JS` in the browser page context
6. Post-processes results: assigns positions, detects sponsored via Python regex
7. Batch-enriches icon URLs via iTunes Lookup API (synchronous, in thread)

### `_EXTRACT_JS` (inline JavaScript)
- Finds all `a[href*="/app/"]` links
- Extracts `app_id` from href pattern `/id(\d{6,})/`
- Deduplicates by app_id
- Walks up 6 DOM levels from the link to find the card container
- Tests card text for sponsored patterns: `/sponsored|search\s+ads|\bAd\b/i`
- Tests card attributes for: `/sponsored|searchads|search-ads/i`
- Extracts `app_name` from heading elements (`h3`, `h2`, `h4`, `[class*="title"]`)
- Extracts `developer` from subtitle elements (`[class*="subtitle"]`, `[class*="developer"]`)
- Extracts icon: tries `srcset` first, then `data-srcset`, then `src` (usually lazy placeholder)

### Sponsored Detection
- **Text-based:** Card inner text contains "Sponsored", "Search Ads", or standalone "Ad"
- **Attribute-based:** Card's `data-testid`, `data-type`, or `className` contains "sponsored", "searchads", "search-ads"
- **Python fallback:** Python-side regex on `app_name + developer` combined text
- **Known limitation:** Heuristic-based; Apple can change ad labeling at any time

### Icon URL Enrichment
- Playwright-scraped icons are lazy-loaded placeholders (`1x1.gif` from Apple CDN)
- After extraction, calls `_fetch_icons(app_ids, country)`:
  - `https://itunes.apple.com/lookup?id={id1,id2,...}&country={country}&entity=software`
  - Maps `trackId → artworkUrl100`
  - Up to 50 app IDs per request

### Key Constants
- `SEARCH_URL = "https://apps.apple.com/{country}/search?q={term}"`  ← uses `?q=`, NOT `?term=`
- `timeout_ms = 30_000` (browser navigation)
- `wait_for_selector timeout = 20_000`
- `MAX_RESULTS_PER_KEYWORD = 20` (in `keyword_rank_tracker.py`)
- `SCRAPE_CONCURRENCY = 2` (parallel pages)

### Fragility Risks
- 🔴 HIGH RISK — Depends on Apple's web page DOM structure
- 🔴 Sponsored detection is heuristic-based; Apple changes ad labeling
- 🔴 Only captures ~16 results per keyword (page load limitation, not pagination)
- ⚠️ Playwright Chromium is a heavy dependency (~100MB browser binary)
- ⚠️ Headless detection: Apple may block automated browsers with CAPTCHA in the future
- ⚠️ Slow: ~5–7 seconds per keyword due to page load + scroll delays
- **URL change history:** `?term=` → 404 (broke in early 2026); fixed to `?q=`

---

## Common Fragility Patterns

| Risk | Affected Scraper | Early Warning Signs | Recovery |
|------|-----------------|---------------------|----------|
| iTunes API schema change | AppStoreScraper, AppStoreAppScraper | Missing fields in returned data | Check Apple Developer docs, update field mappings |
| App Store HTML restructure | AppStoreAppScraper.get_app_versions() | Version history returns 0 versions | Inspect new `<script>` tag JSON structure |
| Search URL format change | AppStoreSearchScraper | 0 results returned, timeout logs | Check what URL format Apple currently uses |
| Sponsored detection break | AppStoreSearchScraper | All `is_sponsored=False` results | Inspect DOM for new ad label patterns |
| Apple blocking Playwright | AppStoreSearchScraper | Consistent empty results or CAPTCHA | Add longer delays, rotate User-Agent, try stealth mode |
| iTunes RSS feed change | AppStoreScraper | Top charts returns 0 results | Check new RSS feed URL format |

---

## Data Source Summary

| Scraper | Data Source | Auth Required | Stability |
|---------|-------------|---------------|-----------|
| AppStoreScraper | iTunes Search API | No | ✅ High |
| AppStoreScraper | iTunes RSS JSON feed | No | ✅ High |
| AppStoreAppScraper | iTunes Lookup API | No | ✅ High |
| AppStoreAppScraper | App Store HTML (versions) | No | 🔴 Low |
| AppStoreAppScraper | iTunes RSS Reviews | No | ✅ High |
| AppStoreSearchScraper | App Store web pages (Playwright) | No | 🔴 Low |
| AppStoreSearchScraper | iTunes Lookup API (icons) | No | ✅ High |
