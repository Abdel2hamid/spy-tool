# Data Pipeline

How data flows from Apple's servers through the system to the frontend.

---

## Data Sources

| Source | Method | Used For |
|---|---|---|
| iTunes Lookup API | HTTP GET `https://itunes.apple.com/lookup?id={id}&country=us` | App metadata, developer info, pricing |
| iTunes Search API | HTTP GET `https://itunes.apple.com/search?term=...&entity=software` | Keyword search, app discovery |
| iTunes RSS JSON feed | HTTP GET `https://itunes.apple.com/us/rss/{chart}/limit={N}/genre={id}/json` | Top charts (topfree, toppaid, topgrossing) |
| iTunes Customer Reviews RSS | HTTP GET `https://itunes.apple.com/{country}/rss/customerreviews/...` | App reviews by storefront |
| App Store HTML (version history) | HTTP GET `https://apps.apple.com/{country}/app/id{id}` | Version history via embedded JSON |
| Apple MZSearchHints API | HTTP GET `https://search.itunes.apple.com/WebObjects/MZSearchHints.woa/wa/hints?clientApplication=Software&q={term}` | Keyword autocomplete suggestions |
| Google Trends (pytrends) | Python library | Keyword trend_score, trend_growth, trend_velocity |
| Meta Ads Library API | HTTP GET (optional, requires FACEBOOK_ACCESS_TOKEN) | Ad creative detection |

---

## Phase 1: Discovery

**Purpose:** Find new apps to track without knowing their IDs upfront.

### Sub-pipeline A: Chart Discovery
```
DiscoveryEngine.run_chart_discovery_batch()
  │
  ├── iTunes RSS: topfree + toppaid + topgrossing
  ├── × all genre IDs in _GENRE_IDS dict (~30 genres)
  ├── × 20 country codes
  ├── limit=200 apps per chart
  │
  ▼
  DiscoveryQueue (status=pending, source="chart:...")
```
**Scheduler:** `discovery_charts` — every 2h, first run +5min

### Sub-pipeline B: Keyword Discovery
```
DiscoveryEngine.run_keyword_discovery()
  │
  ├── 100+ seed keywords from config
  ├── iTunes Search API for each keyword
  │
  ▼
  DiscoveryQueue (status=pending, source="keyword:...", priority=2)
```
**Scheduler:** `discovery_keywords` — every 6h, first run +2min

### Sub-pipeline C: Developer Expansion
```
DiscoveryEngine.run_developer_discovery()
  │
  ├── All developer_ids from apps table
  ├── iTunes developer lookup → all apps by developer
  │
  ▼
  DiscoveryQueue (status=pending, source="developer:...", priority=1)
```
**Scheduler:** `discovery_developer` — every 12h, first run +10min

### Queue Processing
```
DiscoveryEngine.process_queue(batch_size=25)
  │
  ├── Read pending items: ORDER BY priority DESC, added_at DESC
  ├── ScraperWorker.scrape_app_full_details(app_id_str)
  │     ├── iTunes Lookup API → app metadata
  │     ├── iTunes RSS → reviews (up to 10 storefronts)
  │     └── App Store HTML → version history
  │
  ▼
  apps table (upsert by app_id)
  rankings table (new row per scrape if ranked)
  reviews table (insert new reviews by review_id UNIQUE)
  app_versions table (upsert by app_id + version)
```
**Scheduler:** `queue_processor` — every 30min, first run +15min

---

## Phase 2: Data Ingestion (Scraping)

### Full Metadata Scrape
```
ScraperWorker.scrape_all_tracked_apps()
  │
  ├── Query: all App rows
  ├── For each: scrape_app_full_details(app.app_id)
  │     ├── iTunes Lookup API
  │     │     → name, subtitle, description, developer, icon_url
  │     │     → price, is_free, rating, review_count, category
  │     │     → version, release_date, last_updated, languages
  │     ├── iTunes RSS Customer Reviews
  │     │     → Reviews for US + top storefronts
  │     │     → Sentiment tagging: positive (≥4★) / neutral (3★) / negative (≤2★)
  │     └── App Store HTML version history
  │           → Embedded JSON scrape for mostRecentVersion
  │           → Parses version, date, release notes
  │
  ▼
  updates apps, rankings, reviews, app_versions tables
```
**Scheduler:** `full_metadata` — every 6h, first run +6h

### Quick Refresh (Lightweight)
```
ScraperWorker.scrape_quick_refresh_all()
  │
  ├── iTunes Lookup API only (no reviews, no versions)
  ├── Updates: rating, review_count, rank, last_updated
  │
  ▼
  updates apps.current_rating, current_reviews, current_rank
```
**Scheduler:** `hourly_reviews_ratings` — every 1h, first run +1h

### Review Scraper (Deep)
```
ReviewScraperService.run()
  │
  ├── Top 300 ranked apps
  ├── Up to 500 reviews per app (multiple storefronts)
  ├── iTunes RSS: pages 1–10 per storefront
  │
  ▼
  reviews table (insert, dedup by review_id)
```
**Scheduler:** `review_scraper` — every 6h, first run +90min

---

## Phase 3: Scoring & Enrichment

All scoring runs after data ingestion. Entry point: `ScoringWorker.update_opportunities()`.

### Sentiment Analysis
```
ReviewSentimentService.run_all()
  │
  ├── Rule-based: rating ≥4 → positive, rating 3 → neutral, rating ≤2 → negative
  ├── Updates reviews.sentiment column
  │
  ▼
  reviews.sentiment (positive/neutral/negative)
```
**Scheduler:** `sentiment_analysis` — every 1h, first run +35min

### Feature Gap Analysis
```
FeatureGapAnalyzer.compute_for_all()
  │
  ├── Negative reviews (rating ≤2) per app
  ├── Text pattern matching for feature requests
  ├── Aggregates by feature_name + mention count
  │
  ▼
  feature_gaps table (upsert by app_id + feature_name)
```
**Scheduler:** `feature_gap` — every 2h, first run +50min

### App Analytics Roll-up
```
AppAnalyticsService.compute_for_all()
  │
  ├── review_growth_30d, review_growth_90d (% change)
  ├── rating_change_30d, rating_change_90d
  ├── Aggregated positive_themes, bug_keywords, common_complaints
  │
  ▼
  app_analytics table
```
**Scheduler:** `analytics_update` — every 2h, first run +55min

### Market Weakness
```
ScoringEngine.compute_market_weakness(app_id)
  │
  ├── Groups reviews by storefront (country)
  ├── Excludes countries with < 20 reviews
  ├── Computes negative_ratio per country
  │
  ▼
  app_market_weakness table (upsert by app_id + country)
```
Also computed on-demand via `GET /apps/{id}/market-weakness`.

### Opportunity Scoring
```
ScoringWorker.update_opportunities()
  │
  ├── ScoringEngine.compute_opportunities_for_all()
  │     → opportunities table
  ├── IdeaGenerator.generate_all()
  │     → app_ideas table (upsert by idea_title)
  ├── InstallEstimator.compute_all() (legacy)
  │     → updates apps.estimated_installs_* columns
  ├── RevenueEstimator.compute_all()
  │     → updates apps.estimated_revenue_monthly_* columns
  │
  ▼
  DailyReport (upsert for today)
```
**Scheduler:** `hourly_scoring` — every 1h, first run +65min (after quick refresh)

---

## Phase 4: Precomputed Scores

### Trending Score Computation
```
TrendingComputeService.compute_trending_scores(db)
  │
  ├── Query apps with ≥2 ranking snapshots in last 14d
  ├── For each: ScoringEngine.compute_trend_score()
  │     - momentum_3d, momentum_7d: rank change over window
  │     - consistency_score: how sustained the trend is
  │     - absolute_rank_bonus: position ≤ 50 gets bonus
  │     - review_momentum: new reviews/day normalized
  │     - confidence_factor: sparse data penalty
  ├── trend_score = weighted blend of above
  │
  ▼
  app_trending_scores (PG upsert ON CONFLICT DO UPDATE)
```
**Scheduler:** `trending_compute` — every 10min, first run +2min

### Blowing Up Score Computation
```
BlowingUpService.compute_for_all_apps()
  │
  ├── Query apps with recent ranking history
  ├── For each: score 6 components (velocity, change, reviews, etc.)
  ├── Generate badges + why_flagged lists
  │
  ▼
  app_blowing_up_scores (upsert)
```
**Scheduler:** `blowing_up_compute` — every 15min, first run +3min

### Opportunity of Day
```
ScoringEngine.compute_opportunity_of_day()
  │
  ├── Find top-scoring opportunity in opportunities table
  ├── Cross-reference trending + keyword data
  │
  ▼
  daily_reports (upsert for today)
```
**Scheduler:** `opportunity_compute` — every 1h, first run +5min

---

## Phase 5: Estimation Pipeline

### Download + Revenue Estimation
```
DownloadEstimator(db).estimate(app_id)
  │
  ├── _gather_signals(app) — single DB round-trip
  │     collects: ranking_history_days, review_velocity,
  │               keyword_count, keyword_avg_opportunity, trending_score
  │
  ├── L1: _layer1_rank_curve(signals)
  │     → get (lo, hi) from rank_curves.interpolate_rank_downloads(rank, category)
  │     → return midpoint as daily estimate
  │
  ├── L2: _layer2_review_velocity(signals)
  │     → velocity × ir_ratio × calibration_factor
  │     → cap at 500 reviews/day anti-spam
  │
  ├── L3: _layer3_visibility(signals)
  │     → keyword_count × avg_opportunity / 100 → footprint
  │     → base_daily = 100 + footprint × scaling_factor
  │
  ├── L4: _layer4_momentum(signals)
  │     → adjustment ∈ [-0.30, +0.20] from trending data
  │
  ├── _compute_weights(signals) — dynamic rebalancing if signals missing
  │     default: rank=0.45, review=0.25, visibility=0.20, momentum=0.10
  │
  ├── daily_base = (w_rank×L1 + w_review×L2 + w_vis×L3) × (1 + L4)
  │
  ├── ConfidenceEngine.compute(signals)
  │     → product of 5 factors capped by category_ceiling
  │
  ├── uncertainty = 0.30 + (1 - confidence) × 0.70
  │
  ├── monthly = daily_base × 30
  ├── range = monthly × (1 ± uncertainty)
  │
  ├── Apply calibration_profiles[category]
  ├── Anti-manipulation: cap at 10× category average
  ├── Floor: 10 downloads/day
  │
  ▼
  Returns rich dict with factor_breakdown + estimation_notes

RevenueEstimator._compute_from_installs(app, dl_low, dl_high)
  │
  ├── get_arpu_profile(app.primary_category)
  │     → arpu_low, arpu_medium, arpu_high
  │     → primary_model: iap / subscription / ad-driven
  │     → active_fraction: % of installs that are monthly active
  │     → iap_conversion_rate
  │
  ├── active_users = monthly_installs × active_fraction
  ├── revenue = active_users × arpu × iap_conversion_rate
  │
  ▼
  Returns estimated_revenue_monthly_min, _max, monetization_model_hint
```
**Triggered:** By `MetricSnapshotService` on each scoring cycle + on-demand via API

---

## Phase 6: Keyword Intelligence Pipeline

```
KeywordIntelligencePipeline.run_full_pipeline(max_keywords=300)
  │
  ├── Phase A: Google Trends enrichment
  │     - pytrends.build_payload() for each keyword
  │     - trend_score = avg interest, trend_growth = 4wk vs prior 4wk
  │     - trend_velocity = last week vs recent avg
  │     - Stores weekly points in keyword_trends (sparklines)
  │     - NOTE: May fail on Railway (cloud IP blocks)
  │
  ├── Phase B: Apple iTunes signals
  │     - iTunes Search API: count results for keyword
  │     - apps_count = number of results
  │     - dominance_score = top-app market share
  │     - marks last_enriched on keyword
  │
  ├── Phase C: Opportunity scoring
  │     - opportunity_score = vol_pts + diff_pts + trend_pts + comp_pts
  │     - feasibility_score = diff_pts + scarcity_pts + ads_pts + gap_pts + trend_pts
  │     - brand penalty if dominance_score ≥ 80
  │
  ▼
  keywords table (bulk update)
```
**Scheduler:** Part of `hourly_scoring` via `ScoringWorker`

---

## Phase 7: Ad Intelligence

```
AdIntelligenceService.scan_candidate_apps(db)
  │
  ├── Candidates: apps with blowing_up_score > 30 OR trending_score > 40
  ├── For each candidate:
  │     - Apple Search Ads signal: infer from rank + reviews correlation
  │     - Optional Meta Ads Library: GET ads for app (requires token)
  │     - Creates AdCreative + AdCampaign rows
  │
  ├── CampaignTrackingService.detect_for_all(db)
  │     - Reads: app_metric_snapshots, ad_campaigns, app_trending_scores
  │     - Classifies event_type based on signal combination:
  │         paid_push: strong ad evidence + rank surge
  │         organic_breakout: rank/reviews surge, no ads
  │         mixed: both signals present
  │         momentum_surge: unusual velocity, unclear cause
  │         campaign_cooling: ad declining after paid_push period
  │         unknown_unusual: anomaly without clear classification
  │
  ▼
  ad_creatives, ad_campaigns, growth_events tables
```
**Scheduler:** `ad_intelligence` — every 6h; `campaign_detection` — every 2h

---

## Current Pipeline Status

| Pipeline | Status | Notes |
|---|---|---|
| Chart discovery | ✅ Operational | iTunes RSS, 20 countries |
| Keyword discovery | ✅ Operational | 100+ seeds, autocomplete |
| Developer expansion | ✅ Operational | Auto-fans out from known devs |
| Queue processing | ✅ Operational | 25 apps/batch, every 30min |
| Full metadata scrape | ✅ Operational | 6h cycle |
| Quick refresh | ✅ Operational | 1h cycle |
| Review deep scrape | ✅ Operational | 6h cycle, 500 reviews/app |
| Sentiment tagging | ✅ Operational | Rule-based, 1h cycle |
| Feature gap analysis | ✅ Operational | 2h cycle |
| Analytics roll-up | ✅ Operational | 2h cycle |
| Trending compute | ✅ Operational | 10min cycle |
| Blowing Up compute | ✅ Operational | 15min cycle |
| Download estimation | ✅ Operational | On scoring cycle + on-demand |
| Revenue estimation | ✅ Operational | On scoring cycle + on-demand |
| Keyword intelligence pipeline | ⚠️ Partial | Google Trends blocked on Railway |
| Keyword rank tracking | ⚠️ Partial | Playwright may not run on Railway |
| Ad intelligence | ⚠️ Partial | Heuristic only; Meta requires token |
| Campaign tracking | ✅ Operational | Derives from existing signals |

---

## Missing Operational Pieces

1. **Real-time notifications** — no webhook or push when scores spike
2. **Multi-country charts** — only US charts by default; multi-country is in DiscoveryEngine but not guaranteed coverage
3. **Paid data sources** — DataForSEO flag exists but no implementation; Apple Search Ads API not used (only heuristic)
4. **Data retention policy** — `app_metric_snapshots` kept forever; no cleanup job; ranking history kept 90d max on queries but not purged from DB
5. **Backfill gap** — installing on an existing populated DB won't retroactively compute metric snapshots for all apps

---

*Documentation generated by auditing the current codebase. Last updated: 2026-03-17.*
