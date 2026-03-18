# Database Schema

PostgreSQL database. Tables are auto-created by `Base.metadata.create_all()` on startup, plus additive `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migrations in `_MIGRATIONS` (see `backend/app/main.py`).

**Source files:**
- Models: `backend/app/models/models.py`
- Migrations: `backend/app/main.py` (`_MIGRATIONS` list)

---

## Core Entities

### `apps`
Primary entity. One row per tracked iOS app.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | DB auto-increment |
| app_id | String(100) UNIQUE | iTunes numeric trackId (string) |
| name | String(500) | App display name |
| subtitle | String(500) | App subtitle |
| description | Text | Full description |
| developer | String(500) | Developer name |
| developer_id | String(100) | iTunes developer ID |
| icon_url | String(512) | App icon CDN URL |
| screenshots | JSON | List of screenshot URLs |
| primary_category | String(255) | Main App Store category |
| secondary_category | String(255) | Second category if any |
| price | Float | 0 for free apps |
| currency | String(10) | Default "USD" |
| is_free | Boolean | True if price == 0 |
| in_app_purchases | JSON | IAP descriptions |
| current_version | String(50) | Latest version string |
| minimum_ios_version | String(50) | Minimum iOS requirement |
| supported_languages | JSON | Language list |
| release_date | DateTime(tz) | Original release date |
| last_updated | DateTime(tz) | Last app update date |
| content_rating | String(50) | Age rating |
| current_rating | Float | Average star rating |
| current_reviews | Integer | Total review count |
| current_rank | Integer | Current chart rank (nullable) |
| category_id | FK → categories | Linked category |
| url | String(512) | App Store URL |
| estimated_installs_min | Integer | Cached download estimate low |
| estimated_installs_max | Integer | Cached download estimate high |
| install_confidence | Float | Confidence score (0-1) |
| estimated_revenue_monthly_min | Float | Cached revenue estimate low |
| estimated_revenue_monthly_max | Float | Cached revenue estimate high |
| freshness_score | Float | 0–100; 100 = released <30d ago |
| created_at | DateTime(tz) | When first added to DB |
| updated_at | DateTime(tz) | Last DB update |

**Indexes:** category_rank composite, rating, reviews, rank, release_date, created_at, freshness_score, developer, primary_category

---

### `categories`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| name | String(255) UNIQUE | Display name |
| slug | String(255) UNIQUE | URL-safe slug |
| icon | String(512) | |
| created_at | DateTime(tz) | |

---

### `rankings`
Time-series chart rank snapshots. One row per (app, chart, date).

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| category_id | FK → categories | Chart category |
| chart_type | String(50) | topfree / toppaid / topgrossing |
| rank | Integer | Position (1 = #1) |
| previous_rank | Integer | Rank in previous snapshot |
| rank_velocity | Float | Positive = improving; negative = dropping |
| recorded_at | DateTime(tz) | Snapshot timestamp |

**Indexes:** (app_id, recorded_at), (chart_type, recorded_at)

---

### `reviews`
Individual app reviews from iTunes RSS API.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| review_id | String(100) UNIQUE | iTunes review ID |
| user_name | String(255) | |
| rating | Integer | 1–5 stars |
| title | String(500) | |
| content | Text | Full review text |
| date | DateTime(tz) | Review date |
| app_version | String(50) | App version at time of review |
| storefront | String(10) | Country code (us, gb, de, etc.) |
| is_updated | Boolean | Whether reviewer updated rating |
| developer_reply_text | Text | Developer response |
| developer_reply_date | DateTime(tz) | |
| helpful_count | Integer | |
| sentiment | String(20) | positive / neutral / negative (rule-based) |
| created_at | DateTime(tz) | |

**Indexes:** (app_id, date), (app_id, sentiment)

---

### `app_versions`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| version | String(50) | Version string |
| release_date | DateTime(tz) | |
| release_notes | Text | Changelog |
| is_latest | Boolean | |
| created_at | DateTime(tz) | |

---

### `app_analytics`
Computed review analytics roll-up. Updated by `analytics_update` scheduler job.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| review_growth_30d | Float | % growth vs prior period |
| review_growth_90d | Float | |
| rating_change_30d | Float | Rating delta |
| rating_change_90d | Float | |
| sentiment_score | Float | 0-100 positive sentiment |
| sentiment_label | String(50) | positive/neutral/negative |
| common_complaints | JSON | List of complaint strings |
| common_features | JSON | Requested features |
| positive_themes | JSON | |
| bug_keywords | JSON | Bug-related terms |
| churn_risk_score | Float | 0-100 |
| update_cadence_score | Float | |
| quality_score | Float | |
| opportunity_score | Float | |
| computed_at | DateTime(tz) | |

---

## Keyword Intelligence

### `keywords`
Central keyword dictionary.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| term | String(255) UNIQUE | The keyword text |
| search_volume | Integer | Legacy estimate |
| difficulty | Float | Legacy 0–100 |
| trend | Float | Legacy trend value |
| last_updated | DateTime(tz) | |
| trend_score | Float | Google Trends avg (0-100) |
| trend_growth | Float | % growth 4wk vs prior 4wk |
| trend_velocity | Float | Last week vs recent avg |
| apps_count | Integer | iTunes search result count |
| dominance_score | Float | Top-app market dominance (0-100) |
| competition_score | Float | DataForSEO competition index |
| cpc | Float | Cost per click (USD) |
| opportunity_score | Float | 0-100 composite |
| feasibility_score | Float | 0-100 indie entry feasibility |
| last_enriched | DateTime(tz) | Last pipeline run |
| keyword_source | String(50) | seed / discovery_engine / user |
| discovered_from | String(255) | Parent seed term |
| first_seen_at | DateTime(tz) | |
| status | String(20) | raw / enriched / pruned |
| quality_score | Float | 0-100 composite quality |
| quality_tier | String(1) | A / B / C |
| validation_score | Float | Apple component (0-25) |
| relevance_score | Float | App-context overlap (0-5) |
| canonical_term | String(255) | Normalized for dedup |
| last_seen_at | DateTime(tz) | |
| times_seen | Integer | Discovery count |

---

### `keyword_metrics`
1:1 with keywords. Normalized metrics separated from the dictionary.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| keyword_id | FK UNIQUE → keywords | |
| search_volume | Integer | |
| difficulty | Float | |
| trend_score | Float | |
| last_updated | DateTime(tz) | |

---

### `app_keywords`
App ↔ keyword relationship. Both legacy (position/relevance) and new (rank/traffic/opportunity_score) columns coexist.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| keyword_id | FK → keywords | |
| position | Integer | Legacy: search position |
| relevance | Float | Legacy: relevance score |
| rank | Integer | App's position in iTunes for this keyword |
| traffic | Float | Estimated traffic score |
| opportunity_score | Float | |
| source | String(50) | extracted / discovered / alphabet / competitor |
| created_at | DateTime(tz) | |

**Unique:** (app_id, keyword_id)

---

### `app_keyword_intelligence`
Per-app keywords extracted from title/subtitle/description + enriched via iTunes.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| keyword_id | FK → keywords | |
| source | String(50) | title / subtitle / description |
| app_rank | Integer | App's position in iTunes results for this keyword |
| result_count | Integer | Total iTunes results |
| search_volume | Integer | Heuristic 0-100 |
| difficulty | Float | Heuristic 0-100 |
| traffic_score | Float | search_volume × CTR(rank) |
| extracted_at | DateTime(tz) | |

**Unique:** (app_id, keyword_id)

---

### `app_discovered_keywords`
Keywords discovered per app via autocomplete expansion.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| keyword | String(255) | Keyword text |
| source | String(50) | autocomplete / prefix / suffix / alphabet / competitor |
| source_keyword | String(255) | Seed that generated this |
| search_volume | Integer | |
| difficulty | Float | |
| traffic_score | Float | |
| app_rank | Integer | App's position for this keyword |
| competitor_rank | Integer | Best competitor position in top-10 |
| keyword_gap | Boolean | True if competitor ≤10 AND app ranks >30 |
| trend_score | Float | |
| trend_direction | String(20) | rising / stable / declining |
| opportunity_score | Float | |
| created_at | DateTime(tz) | |

**Unique:** (app_id, keyword)

---

### `keyword_search_snapshots`
Point-in-time App Store search result captures (used for rank tracking + ads detection).

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| keyword | String(255) | |
| country | String(10) | Default "us" |
| app_id | String(100) | App Store ID (not FK — may not be in apps table) |
| app_name | String(500) | |
| developer | String(500) | |
| icon_url | String(512) | |
| position | Integer | 1-based position on page |
| organic_position | Integer | Position among non-sponsored results |
| is_sponsored | Boolean | Whether this is an ad |
| captured_at | DateTime(tz) | |

---

### `keyword_trends`
Weekly Google Trends interest data (sparklines).

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| keyword_id | FK → keywords | |
| week_start | DateTime(tz) | Monday of the week |
| interest_score | Integer | 0–100 relative interest |
| captured_at | DateTime(tz) | |

**Unique:** (keyword_id, week_start)

---

### `keyword_queue`
Decouples keyword discovery from enrichment. Written by DiscoveryEngine; drained by pipeline.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| term | String(255) UNIQUE | |
| status | String(20) | pending / enriching / done / failed |
| priority | Integer | Higher = processed first |
| source | String(50) | discovery_engine / seed / user |
| added_at | DateTime(tz) | |
| processed_at | DateTime(tz) | |

---

## Opportunity & Intelligence

### `opportunities`
Computed market opportunities linked to apps.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| opportunity_type | String(50) | Type of opportunity |
| primary_keyword | String(255) | |
| competition_score | Float | |
| trend_score | Float | |
| success_probability | Float | 0–100 |
| ai_integration_potential | Float | |
| recommendation | Text | Human-readable recommendation |
| generated_at | DateTime(tz) | |

---

### `app_ideas`
AI-generated app opportunity cards.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| idea_title | String(500) UNIQUE | Upsert key |
| idea_description | Text | |
| opportunity_score | Float | 0–100 |
| pattern_type | String(50) | feature_gap / weak_market / keyword_gap |
| related_app_ids | JSON | List of app IDs |
| reasoning | JSON | List of reasoning strings |
| signals | JSON | Signal dict |
| primary_keyword | String(255) | |
| category | String(255) | |
| generated_at | DateTime(tz) | |
| updated_at | DateTime(tz) | |

---

### `feature_gaps`
Features users request in reviews (extracted by pattern matching on negative reviews).

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| feature_name | String(255) | |
| mentions | Integer | Times mentioned in reviews |
| detected_at | DateTime(tz) | |

**Unique:** (app_id, feature_name)

---

### `app_market_weakness`
Per-country negative review analysis.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| country | String(10) | Country code (us, gb, de, …) |
| total_reviews | Integer | Reviews from this country |
| negative_reviews | Integer | |
| average_rating | Float | |
| negative_ratio | Float | 0–1; negative_reviews / total |
| computed_at | DateTime(tz) | |

**Unique:** (app_id, country)

---

### `daily_reports`
Precomputed daily opportunity-of-day.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| date | DateTime(tz) UNIQUE | |
| top_trending_apps | JSON | |
| opportunity_of_day | JSON | Full opportunity detail dict |
| category_insights | JSON | |
| generated_at | DateTime(tz) | |

---

## Growth Intelligence

### `app_trending_scores`
Precomputed trending scores. Primary key = app_id (1:1 with apps).

| Column | Type | Notes |
|---|---|---|
| app_id | FK PK → apps | |
| trend_score | Float | 0–100 composite |
| momentum_score | Float | Weighted blend (3d/7d/14d) |
| momentum_3d | Float | Raw 3-day |
| momentum_7d | Float | Raw 7-day |
| consistency_score | Float | |
| absolute_rank_bonus | Float | Top-50 bonus |
| review_momentum | Float | Normalized new reviews/day |
| confidence_factor | Float | 0–1 data quality penalty |
| computed_at | DateTime(tz) | |

---

### `app_blowing_up_scores`
Precomputed momentum scores. Primary key = app_id (1:1 with apps).

| Column | Type | Notes |
|---|---|---|
| app_id | FK PK → apps | |
| blowing_up_score | Float | 0–100 composite |
| rank_velocity_score | Float | 0–100 |
| rank_change_score | Float | 0–100 |
| reviews_velocity_score | Float | 0–100 |
| chart_presence_score | Float | 0–100 |
| cross_market_score | Float | 0–100 |
| consistency_score | Float | 0–100 |
| confidence_score | Float | 0–100 |
| rank_change | Integer | Rank improvement (positive = better) |
| rank_velocity | Float | Avg velocity |
| reviews_velocity | Float | Reviews/day |
| chart_appearances | Integer | Ranking snapshots in window |
| markets_count | Integer | Distinct chart types + categories |
| badges | JSON | ["Rapid Climb", "Fast Reviews", …] |
| why_flagged | JSON | Human-readable explanations |
| computed_at | DateTime(tz) | |

---

### `app_metric_snapshots`
Time-series download + revenue estimate snapshots. Appended on every scoring cycle.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| snapshot_at | DateTime(tz) | Snapshot timestamp |
| estimated_downloads_min | Integer | |
| estimated_downloads_max | Integer | |
| install_confidence | Float | |
| estimated_revenue_monthly_min | Float | |
| estimated_revenue_monthly_max | Float | |
| revenue_confidence | Float | |
| monetization_model | String(50) | paid_$x / free+iap / free_ads_only |
| has_ads_signal | Boolean | Ad activity detected |
| campaign_confidence | Float | 0–1 |
| source_signals | JSON | All signals used (for audit) |

---

### `ad_creatives`
Individual ad creative records.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| network | String(50) | apple_search_ads / meta / google_uac |
| external_creative_id | String(255) | Network's creative ID |
| format | String(50) | banner / video / interstitial / native |
| creative_url | Text | |
| title | Text | Ad headline |
| body | Text | Ad copy |
| cta | String(100) | Call to action |
| first_seen_at | DateTime(tz) | |
| last_seen_at | DateTime(tz) | |
| is_active | Boolean | |
| raw_payload | JSON | Full network response |

**Unique:** (app_id, network, external_creative_id)

---

### `ad_campaigns`
Campaign-level aggregation.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| network | String(50) | |
| campaign_key | String(255) | Stable identifier per network |
| first_seen_at | DateTime(tz) | |
| last_seen_at | DateTime(tz) | |
| active_creatives_count | Integer | |
| countries | JSON | Country codes |
| status | String(20) | active / inactive / paused / unknown |
| campaign_confidence | Float | 0–1 |

**Unique:** (app_id, network, campaign_key)

---

### `growth_events`
Growth signal classification events.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | FK → apps | |
| detected_at | DateTime(tz) | |
| event_type | String(50) | paid_push / organic_breakout / mixed / momentum_surge / campaign_cooling / unknown_unusual |
| confidence | Float | 0–1 |
| explanation | Text | Human-readable |
| signals | JSON | Raw signal dict |
| started_at_estimate | DateTime(tz) | Estimated campaign start |
| active_status | Boolean | Is event still active |

---

## Infrastructure Tables

### `discovery_queue`
App IDs awaiting full scrape.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| app_id | String(100) UNIQUE | iTunes numeric ID |
| status | String(20) | pending / scraping / done / failed |
| priority | Integer | Higher = processed first |
| source | String(255) | e.g., "chart:topfreeapplications:us:6007" |
| failed_attempts | Integer | |
| added_at | DateTime(tz) | |
| processed_at | DateTime(tz) | |

---

### `discovery_progress`
Tracks which sources have been crawled.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| source_key | String(255) UNIQUE | e.g., "chart:topfreeapplications:us:6007" |
| last_run | DateTime(tz) | Last time this source was crawled |
| apps_found | Integer | Cumulative IDs found |

---

## Schema Notes & Inconsistencies

1. **Dual estimation columns on `apps`:** `estimated_installs_min/max` (legacy, cached from `InstallEstimator`) + `estimated_revenue_monthly_min/max` are point-in-time; `app_metric_snapshots` is the time-series version. Frontend prefers the time-series endpoint.

2. **`keyword_search_snapshots.app_id` is a String, not FK:** Because snapshots may reference apps not yet imported into the DB.

3. **`app_keywords` has both legacy columns (position, relevance) and new columns (rank, traffic, opportunity_score):** The legacy columns are from the old keyword search tracker; new columns from the target architecture. Both coexist.

4. **No Alembic** — schema evolution is additive-only via `_MIGRATIONS`. Dropping columns or renaming tables requires manual intervention.

5. **`keywords` table is bloated** — quality_score, quality_tier, validation_score, canonical_term, etc. were added iteratively. `keyword_metrics` was created to normalize but the separation is incomplete.

---

*Documentation generated by auditing the current codebase. Last updated: 2026-03-17.*
