# Database Schema

PostgreSQL database: `appstore_spy`

All tables are auto-created by SQLAlchemy's `Base.metadata.create_all(bind=engine)` on startup.

---

## Entity Relationship Overview

```
categories ──< apps >── rankings
                │
                ├──< reviews
                ├──< app_versions
                ├──< app_analytics
                ├──< app_keywords >── keywords
                ├──< opportunities
                ├──< app_market_weakness
                └──< feature_gaps

keyword_search_snapshots   (standalone — app_id is a string, not FK)
app_ideas                  (standalone — related_app_ids is JSON, not FK)
daily_reports              (standalone — JSON blobs)
```

---

## Table: `categories`

Stores App Store genre taxonomy (Productivity, Games, Health & Fitness, etc.)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `name` | VARCHAR unique | e.g., "Productivity" |
| `slug` | VARCHAR unique | e.g., "productivity" |
| `icon` | VARCHAR nullable | Icon character or URL |
| `created_at` | DATETIME | Server default: now() |

**Relationships:** One category → many apps, many rankings

---

## Table: `apps`

Core entity. One row per tracked App Store app.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Internal DB ID |
| `app_id` | VARCHAR unique | App Store string ID (e.g., "553834731") |
| `name` | VARCHAR | App display name |
| `subtitle` | VARCHAR nullable | App subtitle |
| `description` | TEXT nullable | Full description |
| `developer` | VARCHAR nullable | Developer name |
| `developer_id` | VARCHAR nullable | Apple developer account ID |
| `icon_url` | VARCHAR nullable | App icon URL |
| `screenshots` | JSON nullable | Array of screenshot URLs |
| `primary_category` | VARCHAR nullable | e.g., "Productivity" |
| `secondary_category` | VARCHAR nullable | |
| `category_id` | INTEGER FK(categories) nullable | |
| `price` | FLOAT default 0 | Price in USD |
| `currency` | VARCHAR default "USD" | |
| `is_free` | BOOLEAN default true | |
| `in_app_purchases` | JSON nullable | Structured IAP data |
| `current_version` | VARCHAR nullable | e.g., "3.57.1" |
| `minimum_ios_version` | VARCHAR nullable | |
| `supported_languages` | JSON nullable | Array of language codes |
| `release_date` | DATETIME nullable | Initial release date |
| `last_updated` | DATETIME nullable | Last version update |
| `content_rating` | VARCHAR nullable | e.g., "4+" |
| `current_rating` | FLOAT nullable | Average rating (1.0-5.0) |
| `current_reviews` | INTEGER nullable | Total review count |
| `current_rank` | INTEGER nullable | Latest chart rank |
| `url` | VARCHAR nullable | App Store URL |
| `created_at` | DATETIME | Server default: now() |
| `updated_at` | DATETIME | Server default: now(), onupdate: now() |

**Indexes:** `(category_id, current_rank)`, `app_id` (unique)

**Relationships:** rankings, reviews, keywords (via app_keywords), opportunities, versions, analytics, market_weakness, feature_gaps

---

## Table: `rankings`

Point-in-time chart position snapshot for each app.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `app_id` | INTEGER FK(apps) | |
| `category_id` | INTEGER FK(categories) nullable | |
| `chart_type` | VARCHAR | `topfreeapplications`, `toppaidapplications`, `topgrossingapplications` |
| `rank` | INTEGER | Current position (1-based) |
| `previous_rank` | INTEGER nullable | Previous captured position |
| `rank_velocity` | FLOAT default 0 | `previous_rank - rank` (positive = rising) |
| `recorded_at` | DATETIME | Server default: now() |

**Indexes:** `(app_id, recorded_at)`, `(chart_type, recorded_at)`

---

## Table: `reviews`

Individual App Store user reviews.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `app_id` | INTEGER FK(apps) | |
| `review_id` | VARCHAR unique nullable | Apple's unique review ID (dedup key) |
| `user_name` | VARCHAR nullable | |
| `user_url` | VARCHAR nullable | Apple profile URL |
| `rating` | INTEGER nullable | 1–5 stars |
| `title` | VARCHAR nullable | Review headline |
| `content` | TEXT nullable | Full review text |
| `date` | DATETIME nullable | Review date |
| `app_version` | VARCHAR nullable | App version at time of review |
| `storefront` | VARCHAR nullable | Country code (e.g., "US", "DE") |
| `is_updated` | BOOLEAN default false | Whether review was later updated |
| `developer_reply_text` | TEXT nullable | Developer's response |
| `developer_reply_date` | DATETIME nullable | |
| `helpful_count` | INTEGER default 0 | |
| `created_at` | DATETIME | Server default: now() |

**Indexes:** `(app_id, date)`

---

## Table: `app_versions`

Version history entries for each app.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `app_id` | INTEGER FK(apps) | |
| `version` | VARCHAR | e.g., "3.57.1" |
| `release_date` | DATETIME nullable | |
| `release_notes` | TEXT nullable | Changelog text |
| `is_latest` | BOOLEAN default false | Only one row per app is True |
| `created_at` | DATETIME | Server default: now() |

**Indexes:** `(app_id, version)`
**Note:** Before each scrape, all `is_latest` flags for an app are reset to False, then the latest version is set back to True.

---

## Table: `app_analytics`

Computed analytics record per app. Multiple records over time (one per computation run).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `app_id` | INTEGER FK(apps) | |
| `review_growth_30d` | FLOAT default 0 | % new reviews in last 30 days |
| `review_growth_90d` | FLOAT default 0 | % new reviews in last 90 days |
| `rating_change_30d` | FLOAT default 0 | Rating delta vs 30 days ago |
| `rating_change_90d` | FLOAT default 0 | Rating delta vs 90 days ago |
| `sentiment_score` | FLOAT default 0 | Composite sentiment (-1 to 1) |
| `sentiment_label` | VARCHAR nullable | "positive", "neutral", "negative" |
| `common_complaints` | JSON nullable | Array of complaint strings |
| `common_features` | JSON nullable | Array of popular feature strings |
| `positive_themes` | JSON nullable | Array of positive theme strings |
| `bug_keywords` | JSON nullable | Array of bug-related keywords |
| `churn_risk_score` | FLOAT default 0 | 0–100 |
| `update_cadence_score` | FLOAT default 0 | 0–100 (higher = more frequent updates) |
| `quality_score` | FLOAT default 0 | 0–100 |
| `opportunity_score` | FLOAT default 0 | 0–100 |
| `computed_at` | DATETIME | Server default: now() |

**Indexes:** `(app_id, computed_at)`

---

## Table: `keywords`

Tracked search terms with metrics.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `term` | VARCHAR unique | Keyword string |
| `search_volume` | INTEGER default 0 | Estimated monthly searches |
| `difficulty` | FLOAT default 0 | Competition difficulty 0–100 |
| `trend` | FLOAT default 0 | Trend score (positive = growing) |
| `last_updated` | DATETIME | Server default: now(), onupdate: now() |

**Note:** `search_volume` is currently estimated as `app_count × 850` — not real Apple data.

---

## Table: `app_keywords`

Junction table linking apps to keywords with ranking data.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `app_id` | INTEGER FK(apps) | |
| `keyword_id` | INTEGER FK(keywords) | |
| `position` | INTEGER nullable | Search rank for this keyword |
| `relevance` | FLOAT nullable | Computed relevance score (0–1) |

**Indexes:** Unique `(app_id, keyword_id)`

---

## Table: `opportunities`

Scored market opportunity per (app, keyword) pair.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `app_id` | INTEGER FK(apps) nullable | |
| `opportunity_type` | VARCHAR | Classification string |
| `primary_keyword` | VARCHAR nullable | Main keyword for this opportunity |
| `competition_score` | FLOAT default 0 | 0–100 |
| `trend_score` | FLOAT default 0 | 0–100 |
| `success_probability` | FLOAT default 0 | 0–100 composite score |
| `ai_integration_potential` | FLOAT default 0 | 0–100 |
| `recommendation` | TEXT nullable | Human-readable recommendation |
| `generated_at` | DATETIME | Server default: now() |

**Indexes:** `opportunity_type`, `success_probability`

---

## Table: `app_market_weakness`

Per-country negative review ratio for each app.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `app_id` | INTEGER FK(apps) | |
| `country` | VARCHAR | ISO country code (e.g., "DE") |
| `total_reviews` | INTEGER default 0 | Reviews from this country |
| `negative_reviews` | INTEGER default 0 | Reviews with rating ≤ 2 |
| `average_rating` | FLOAT default 0 | Mean rating from this country |
| `negative_ratio` | FLOAT default 0 | `negative_reviews / total_reviews` |
| `computed_at` | DATETIME | Server default: now() |

**Indexes:** Unique `(app_id, country)`, `negative_ratio`
**Note:** Only countries with ≥ 20 reviews are included.

---

## Table: `feature_gaps`

Feature requests extracted from negative reviews via NLP.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `app_id` | INTEGER FK(apps) | |
| `feature_name` | VARCHAR | Normalized feature name (e.g., "dark mode") |
| `mentions` | INTEGER default 0 | Count of distinct reviews mentioning this feature |
| `detected_at` | DATETIME | Server default: now() |

**Indexes:** Unique `(app_id, feature_name)`, `mentions`
**Note:** All rows for an app are deleted and re-inserted each time `compute_for_app()` runs.

---

## Table: `daily_reports`

Daily cached dashboard summary. One row per day.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `date` | DATE unique | Report date |
| `top_trending_apps` | JSON | Array of trending app summaries |
| `opportunity_of_day` | JSON | Full opportunity object |
| `category_insights` | JSON | Category-level data |
| `generated_at` | DATETIME | Server default: now() |

---

## Table: `keyword_search_snapshots`

Point-in-time App Store search result capture per keyword. Core table for keyword rank tracking.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `keyword` | VARCHAR | Search term |
| `country` | VARCHAR default "us" | ISO country code |
| `app_id` | VARCHAR | App Store app ID (string, NOT FK to apps table) |
| `app_name` | VARCHAR(500) nullable | App name at time of capture |
| `developer` | VARCHAR(500) nullable | Developer/subtitle at time of capture |
| `icon_url` | VARCHAR(512) nullable | App icon URL (iTunes CDN) |
| `position` | INTEGER | Absolute position on page (1-based, includes ads) |
| `organic_position` | INTEGER nullable | Position counting only organic results |
| `is_sponsored` | BOOLEAN default false | Apple Search Ads placement |
| `captured_at` | DATETIME | Server default: now() |

**Indexes:** `keyword`, `app_id`, `captured_at`, `(keyword, app_id)`, `(keyword, captured_at)`

**Important:** `app_id` is a VARCHAR (App Store string ID), NOT a foreign key to the `apps` table. Many apps captured in searches may not be tracked apps.

---

## Table: `app_ideas`

AI-generated app opportunity ideas synthesized from competitive signals.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `idea_title` | VARCHAR(500) unique | Deduplication key for upsert |
| `idea_description` | TEXT nullable | Extended description |
| `opportunity_score` | FLOAT default 0 | 0–95 (patterns cap at 95) |
| `pattern_type` | VARCHAR(50) | `feature_gap`, `weak_market`, `keyword_gap` |
| `related_app_ids` | JSON default [] | Array of DB integer app IDs |
| `reasoning` | JSON default [] | Array of reasoning strings |
| `signals` | JSON default {} | Raw signal data used to generate idea |
| `primary_keyword` | VARCHAR(255) nullable | Associated keyword |
| `category` | VARCHAR(255) nullable | App category |
| `generated_at` | DATETIME | Server default: now() |
| `updated_at` | DATETIME | Server default: now(), onupdate: now() |

**Indexes:** `opportunity_score`, `pattern_type`, `category`
**Note:** Upserted using PostgreSQL `ON CONFLICT(idea_title) DO UPDATE` — never duplicated.

---

## Key Relationships Summary

```
App (id=123, app_id="553834731")
 ├── AppVersion × N (version history)
 ├── Review × N (user reviews, deduped by review_id)
 ├── Ranking × N (chart positions over time)
 ├── AppAnalytics × N (computed metrics over time)
 ├── AppKeyword × N ──► Keyword (term, volume, difficulty)
 ├── Opportunity × N (scored opportunities)
 ├── AppMarketWeakness × N (per country)
 └── FeatureGap × N (extracted feature requests)

KeywordSearchSnapshot (separate, app_id is string)
AppIdea (separate, related_app_ids is JSON array)
DailyReport (separate, date-keyed, JSON blobs)
```

---

## Data Volume Estimates (typical)

| Table | Typical Row Count | Growth Rate |
|-------|------------------|-------------|
| apps | 100–1000 | Grows with each discovery run |
| reviews | 10,000–100,000 | Grows hourly |
| rankings | 5,000–50,000 | Grows every 6h per chart/category |
| keyword_search_snapshots | 1,000–50,000 | Grows every 6h × keywords × 20 results |
| app_versions | 1,000–10,000 | Grows slowly |
| feature_gaps | 500–5,000 | Recomputed hourly |
| app_ideas | 10–200 | Upserted hourly, stable count |
| app_market_weakness | 100–2,000 | Recomputed hourly |
