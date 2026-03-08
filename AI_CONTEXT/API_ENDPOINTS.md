# API Endpoints

All backend REST API endpoints. Base URL: `http://localhost:8000/api/v1`

---

## Dashboard

### `GET /dashboard/stats`
Returns 4 KPI counts for the dashboard header.

**Response:**
```json
{
  "total_apps_tracked": 487,
  "total_keywords": 12,
  "trending_apps_count": 34,
  "opportunities_count": 156
}
```

---

## Apps

### `GET /apps`
Paginated, filterable app list. This is the most complex endpoint — supports 19 filter parameters.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `search` | string | Full-text search: name, subtitle, developer, description |
| `category` | string | Category name (partial match) |
| `category_id` | int | Exact category DB ID |
| `developer` | string | Developer name (partial match) |
| `min_rating` | float | Minimum current_rating |
| `max_rating` | float | Maximum current_rating |
| `min_reviews` | int | Minimum current_reviews |
| `max_reviews` | int | Maximum current_reviews |
| `min_rank` | int | Minimum current_rank |
| `max_rank` | int | Maximum current_rank |
| `is_free` | bool | Filter by free/paid |
| `has_in_app_purchases` | bool | Filter by IAP presence |
| `updated_after` / `updated_before` | datetime | Filter by last_updated |
| `released_after` / `released_before` | datetime | Filter by release_date |
| `min_success_probability` | float | Minimum opportunity score |
| `ai_only` | bool | Only apps with AI-related keywords in name/description |
| `weak_market` | string | Country code — only apps with negative_ratio > 0 in that country |
| `min_negative_ratio` | float | Minimum negative_ratio across any country |
| `min_feature_gaps` | int | Minimum count of distinct feature gaps |
| `sort_by` | string | Sort field (see valid fields below) |
| `sort_order` | string | `asc` or `desc` (default: `desc`) |
| `skip` | int | Pagination offset (default: 0) |
| `limit` | int | Page size (default: 20, max: 100) |

**Valid `sort_by` values:** `name`, `rating`, `reviews`, `rank`, `updated`, `created`, `rank_velocity`, `review_growth`, `success_probability`, `release_date`, `price`

**Response:**
```json
{
  "apps": [...AppResponse objects...],
  "total": 487,
  "skip": 0,
  "limit": 20
}
```

---

### `GET /apps/{app_id}`
Single app by DB integer ID.

**Response:** `AppResponse` (all metadata fields, no versions/analytics)

---

### `POST /apps`
Create a new app record manually.

**Body:** `AppCreate` (app_id, name, developer, icon_url, price, currency, category_id)

---

### `PATCH /apps/{app_id}`
Partial update of app fields.

**Body:** `AppUpdate` (all fields optional)

---

### `GET /apps/{app_id}/detail`
Full app detail: metadata + latest 20 version records + most recent analytics.

**Response:** `AppDetailResponse` (extends AppResponse with `versions: []` and `analytics: {}`)

---

### `GET /apps/{app_id}/versions`
All version history for an app.

**Response:** List of `AppVersionResponse` objects (id, version, release_date, release_notes, is_latest)

---

### `GET /apps/{app_id}/reviews`
Paginated reviews with optional rating filter.

**Query Parameters:** `rating` (int 1-5, optional), `skip`, `limit` (default 50)

**Response:** List of `ReviewResponse` objects

---

### `GET /apps/{app_id}/analytics`
Most recent `AppAnalytics` record for the app.

**Response:** `AppAnalyticsResponse` (all growth rates, sentiment, NLP themes, all scores)

---

### `GET /apps/{app_id}/rank-history`
Chart ranking history for a date range.

**Query Parameters:** `days` (int 1-90, default 30), `chart_type` (optional filter)

**Response:**
```json
{
  "dates": ["2026-02-06", "2026-02-07", ...],
  "ranks": [45, 43, 38, ...],
  "chart_type": "topfreeapplications",
  "category_name": "Productivity",
  "current_rank": 12
}
```

---

### `GET /apps/{app_id}/market-weakness`
Per-country negative review analysis. Computes on-demand if table is empty for this app.

**Response:**
```json
{
  "app_id": 123,
  "countries": [
    {
      "country": "DE",
      "total_reviews": 847,
      "negative_reviews": 254,
      "average_rating": 3.1,
      "negative_ratio": 0.30,
      "computed_at": "2026-03-08T10:00:00Z"
    }
  ],
  "total_countries": 5,
  "has_data": true
}
```

---

### `GET /apps/{app_id}/feature-gaps`
Feature gap list from negative reviews. Computes on-demand if empty.

**Response:**
```json
{
  "app_id": 123,
  "feature_gaps": [
    {"feature": "dark mode", "mentions": 47, "detected_at": "..."},
    {"feature": "offline mode", "mentions": 23, "detected_at": "..."}
  ],
  "total_features": 12,
  "total_mentions": 189,
  "has_data": true
}
```

---

### `POST /apps/{app_id}/feature-gaps/analyze`
Force re-run NLP analysis on this app's reviews. Replaces existing gaps.

**Response:** Same as `GET /apps/{app_id}/feature-gaps`

---

### `GET /apps/{app_id}/keyword-intelligence`
Organic vs sponsored keyword breakdown and traffic mix for this app.

**Response:**
```json
{
  "app_id": "553834731",
  "app_name": "Focus Keeper",
  "primary_keyword": "focus timer",
  "confidence": 72,
  "organic_keywords": [
    {"keyword": "focus timer", "rank": 3, "search_volume": 12400, "difficulty": 45.0}
  ],
  "ads_keywords": [
    {"keyword": "pomodoro", "position": 2}
  ],
  "traffic_mix": {"organic": 80, "ads": 20},
  "total_snapshots": 48,
  "last_scanned": "2026-03-08T12:00:00Z"
}
```

---

### `POST /apps/{app_id}/refresh`
Manually trigger a full re-scrape of one app (metadata + versions + reviews).

**Response:**
```json
{"status": "success", "app_id": "553834731", "message": "App refreshed successfully"}
```

---

## Trending & Discovery

### `GET /trending`
Top trending apps sorted by rank velocity.

**Query Parameters:** `limit` (int, default 10, max 50)

**Response:** List of `TrendingAppResponse` objects (id, app_id, name, developer, icon_url, current_rank, rank_velocity, review_growth, rating_velocity, trend_score)

---

### `GET /opportunity-of-day`
Today's highest-scored market opportunity. Reads from cached `DailyReport`.

**Response:** `OpportunityOfDayResponse` (app_id, app_name, primary_keyword, all scores, recommendation text)

---

### `GET /keyword-opportunities`
Keyword opportunities filtered by difficulty range.

**Query Parameters:** `min_difficulty` (float, default 0), `max_difficulty` (float, default 100)

**Response:** List of `KeywordOpportunityResponse` (keyword, search_volume, difficulty, trend, opportunity_score, current_apps)

---

## Opportunities & Keywords

### `GET /opportunities`
All scored `Opportunity` rows.

**Query Parameters:** `min_probability` (float, default 0), `limit` (int, default 50)

**Response:** List of `OpportunityResponse`

---

### `GET /keywords`
Paginated keyword list.

**Query Parameters:** `skip`, `limit` (default 100)

**Response:** List of `KeywordResponse` (id, term, search_volume, difficulty, trend)

---

### `POST /keywords`
Create a new tracked keyword.

**Body:** `KeywordCreate` (term, search_volume, difficulty)

---

## Rankings & Categories

### `GET /rankings`
Raw ranking records.

**Query Parameters:** `app_id` (int, optional), `chart_type` (string, optional), `limit` (default 100)

**Response:** List of `RankingResponse`

---

### `GET /categories`
All category records.

**Response:** List of `{"id": 1, "name": "Productivity", "slug": "productivity"}`

---

## AI App Ideas

### `GET /ideas`
Paginated, filterable AI-generated ideas.

**Query Parameters:** `sort_by` (default: `opportunity_score`), `sort_order` (default: `desc`), `pattern_type` (`feature_gap` | `weak_market` | `keyword_gap`), `category` (string filter), `keyword` (string filter), `skip`, `limit` (max 100)

**Response:**
```json
{
  "ideas": [...AppIdeaResponse objects...],
  "total": 47,
  "skip": 0,
  "limit": 20,
  "last_generated": "2026-03-08T12:00:00Z"
}
```

---

### `POST /ideas/generate`
Trigger IdeaGenerator.generate_all() and return fresh results.

**Response:** Same as `GET /ideas` with defaults

---

## Manual Scraping Triggers

### `POST /scrape/all`
Re-scrape all tracked apps (full metadata + versions + reviews). Runs asynchronously in background.

**Response:**
```json
{"status": "started", "message": "Full scrape initiated for N apps"}
```

---

## Scheduler Control

### `GET /scheduler/status`
Current scheduler state and all registered jobs.

**Response:**
```json
{
  "running": true,
  "jobs": [
    {
      "id": "hourly_reviews_ratings",
      "name": "Every 1h: Reviews & Ratings Refresh",
      "next_run_time": "2026-03-08T14:00:00+00:00",
      "trigger": "interval[1:00:00]"
    }
  ]
}
```

---

### `POST /scheduler/jobs/{job_id}/trigger`
Immediately trigger a scheduled job by its ID.

**Valid job IDs:** `hourly_reviews_ratings`, `hourly_scoring`, `full_metadata`, `discovery`, `keyword_rank_tracker`

**Response:**
```json
{"status": "triggered", "job_id": "keyword_rank_tracker"}
```

---

## Keyword Rank Tracker

### `POST /keyword-tracker/run`
Trigger full keyword rank scan for all tracked keywords.

**Query Parameters:** `country` (default: `us`), `keyword_limit` (default: 50)

**Response:** `KeywordTrackerRunResponse`
```json
{
  "status": "completed",
  "keywords_scanned": 7,
  "total_results": 112,
  "sponsored_results": 3,
  "elapsed_seconds": 19.77
}
```

---

### `POST /keyword-tracker/search`
Scrape a single keyword immediately.

**Query Parameters:** `keyword` (required), `country` (default: `us`)

**Response:** `KeywordTrackerRunResponse` (same as above, `keywords_scanned: 1`)

---

### `GET /keyword-search-snapshots`
Query snapshot history from `keyword_search_snapshots` table.

**Query Parameters:** `keyword` (string filter), `app_id` (string filter), `country` (default: `us`), `is_sponsored` (bool filter), `skip`, `limit` (default 50)

**Response:**
```json
{
  "snapshots": [...KeywordSnapshotDB objects...],
  "total": 160,
  "skip": 0,
  "limit": 50
}
```

---

### `GET /keyword-tracker/traffic-sources`
Organic vs ads traffic mix summary for all apps with snapshot data.

**Response:**
```json
{
  "traffic_sources": [
    {
      "app_id": "553834731",
      "app_name": "Focus Keeper",
      "organic_percent": 85,
      "ads_percent": 15,
      "primary_keyword": "focus timer"
    }
  ]
}
```

---

## Status / Health

### `GET /` (root, not under /api/v1)
Basic health check.

**Response:**
```json
{"name": "AppStore Spy AI", "version": "1.0.0", "status": "running"}
```
