# API Endpoints

All backend REST API endpoints extracted from `backend/app/api/routes.py`.

**Base URL:** `http://localhost:8000/api/v1` (local) or configured via `NEXT_PUBLIC_API_URL` / `BACKEND_URL`

---

## Apps

| Method | Route | Purpose | Key Params |
|---|---|---|---|
| GET | `/apps` | Paginated + filtered app list | search, category, developer, min/max rating/reviews/rank, is_free, has_iap, released_after/before, fresh_only, min_freshness_score, min_success_probability, ai_only, weak_market, min_negative_ratio, min_feature_gaps, min/max_estimated_downloads/revenue, confidence_label, sort_by, sort_order, page, skip, limit |
| GET | `/apps/latest` | Release-based discovery | mode (new_releases\|released_today), limit, offset, category, sort_by |
| GET | `/apps/latest-60-days` | Legacy 60-day release window | limit, offset, category |
| GET | `/apps/blowing-up` | Momentum-ranked apps from precomputed table | limit, skip, sort_by, sort_order, min_confidence, min_reviews_velocity, category, chart_type, timeframe, autocompute |
| GET | `/apps/import` | Smart search: detects URL/ID → direct lookup; else text search local DB + iTunes — never writes to DB directly | q (name, App Store URL, or trackId), limit |
| GET | `/apps/lookup/{track_id}` | Import app by iTunes trackId — writes to DB, triggers enrichment | track_id path |
| GET | `/apps/{app_id}` | Single app by DB integer ID | — |
| POST | `/apps` | Create app record manually | AppCreate body |
| PATCH | `/apps/{app_id}` | Update app fields | AppUpdate body |
| POST | `/apps/{app_id}/refresh` | Force re-scrape a single app | — |
| GET | `/apps/{app_id}/detail` | App + versions + analytics composite | — |
| GET | `/apps/{app_id}/versions` | Version history | — |
| GET | `/apps/{app_id}/reviews` | Reviews with optional rating filter | rating, skip, limit |
| GET | `/apps/{app_id}/analytics` | Review growth + sentiment analytics | — |
| GET | `/apps/{app_id}/rank-history` | Rank time-series | days, chart_type |
| GET | `/apps/{app_id}/market-weakness` | Per-country negative review analysis | — |
| GET | `/apps/{app_id}/feature-gaps` | Feature requests from reviews | — |
| POST | `/apps/{app_id}/feature-gaps/analyze` | Force re-run feature gap analysis | — |

**`/apps/import` response shape** (`AppImportSearchResponse`):
```json
{
  "query": "...",
  "results": [...],
  "total": 0,
  "from_cache": 0,
  "direct_lookup": false,
  "error_hint": null
}
```
- `direct_lookup=true` + `results[0].id > 0` → frontend auto-navigates to `/apps/{id}`
- `direct_lookup=true` + `results=[]` + `error_hint` → Apple lookup failed; show error message
- `direct_lookup=false` → normal text search (may return `source='database'` or `source='app_store'` results)

**`results[]` item `source` values:**
- `"database"` — already tracked in local DB; frontend shows **Open** button
- `"app_store"` — found on iTunes, not yet imported; frontend shows **Import** button
- `"direct_lookup"` — imported via URL/ID; only present when `direct_lookup=true`

**File:** `backend/app/api/routes.py:160`

---

## Download & Revenue Estimation

| Method | Route | Purpose | Notes |
|---|---|---|---|
| GET | `/apps/{app_id}/install-estimate` | Legacy single-layer install estimate | Uses `InstallEstimator` (old) |
| GET | `/apps/{app_id}/revenue-estimate` | Revenue estimate | Uses `RevenueEstimator` |
| GET | `/apps/{app_id}/download-estimate` | **Rich 4-layer ensemble estimate** | Preferred endpoint; uses `DownloadEstimator` + `RevenueEstimator` |

Response for `/download-estimate`:
```json
{
  "app_id": 123,
  "estimated_downloads_daily": 1200,
  "estimated_downloads_monthly": 36000,
  "downloads_range_low": 25200,
  "downloads_range_high": 46800,
  "estimated_revenue_monthly": 54000,
  "revenue_range_low": 37800,
  "revenue_range_high": 70200,
  "estimation_confidence": 0.72,
  "confidence_label": "high",
  "monetization_model_hint": "subscription",
  "factor_breakdown": { ... },
  "estimation_notes": "Estimate driven primarily by rank curve..."
}
```

**File:** `backend/app/api/routes.py:2634`

---

## Trending

| Method | Route | Purpose | Notes |
|---|---|---|---|
| GET | `/trending` | Trending apps from precomputed scores | limit, category_id |
| GET | `/trending/v2` | Same as `/trending` (alias) | limit, category_id |
| GET | `/fresh-risers` | Newly released apps with early traction | mode (fresh_risers\|newest\|hidden_gems), limit, category_id |

**Status field in response:** `success` / `insufficient_data` / `empty`
**File:** `backend/app/api/routes.py:829`

---

## Keywords

| Method | Route | Purpose | Key Params |
|---|---|---|---|
| GET | `/keywords` | Basic keyword list | skip, limit |
| POST | `/keywords` | Add keyword (via GlobalKeywordSink) | KeywordCreate body |
| GET | `/keywords/enhanced` | Full keyword list with scoring | search, classification, sort_by, min_volume, max_difficulty, skip, limit |
| GET | `/keywords/trending` | Keywords with strongest trend signals | limit |
| GET | `/keywords/{term}/detail` | Full keyword detail + competitors | term path, country |
| GET | `/keywords/{term}/trend` | Time-series trend data for keyword | term path, country, days |
| POST | `/keywords/pipeline/run` | Manually trigger keyword intelligence pipeline | — |
| GET | `/keywords/pipeline/debug` | Pipeline health stats | — |
| POST | `/keywords/discovery/run` | Trigger keyword discovery engine (3 phases) | — |
| GET | `/keywords/discovery/status` | Discovery engine stats | — |

**File:** `backend/app/api/routes.py:1133`

---

## App-Level Keyword Intelligence

| Method | Route | Purpose | Notes |
|---|---|---|---|
| GET | `/apps/{app_id}/keyword-intelligence` | Organic vs sponsored keyword ranking mix | Uses `KeywordSearchSnapshots` |
| GET | `/apps/{app_id}/keywords/intelligence` | Keyword extraction from app metadata | source: title/subtitle/description |
| POST | `/apps/{app_id}/keywords/intelligence/extract` | Trigger keyword extraction in background | — |
| GET | `/apps/{app_id}/keywords/discovered` | Keywords found via autocomplete expansion | limit |
| POST | `/apps/{app_id}/keywords/discover` | Trigger keyword discovery for app | Requires extracted keywords first |
| GET | `/apps/{app_id}/keywords/opportunities` | Top keyword opportunities for app | — |
| POST | `/apps/{app_id}/keywords/discover-phase1` | Phase-1 keyword discovery (alphabet + competitor) | — |
| GET | `/apps/{app_id}/keyword-history` | Rank over time for a specific keyword | keyword, country |
| GET | `/apps/{app_id}/keyword-history/keywords` | List tracked keywords for an app | — |

**File:** `backend/app/api/routes.py:2307`

---

## Keyword Rank Tracker

| Method | Route | Purpose |
|---|---|---|
| POST | `/keyword-tracker/run` | Scrape App Store search results for all tracked keywords |
| POST | `/keyword-tracker/search` | Scrape a single keyword immediately |
| GET | `/keyword-search-snapshots` | List captured snapshots | keyword, app_id, is_sponsored, country, skip, limit |
| GET | `/keyword-tracker/traffic-sources` | Organic vs ads traffic mix for all apps |

**File:** `backend/app/api/routes.py:2521`

---

## Opportunities & Intelligence

| Method | Route | Purpose |
|---|---|---|
| GET | `/opportunities` | Computed market opportunities | skip, limit, min_probability |
| GET | `/opportunity-of-day` | Today's precomputed opportunity | — |
| GET | `/keyword-opportunities` | Keyword market opportunities | min_difficulty, max_difficulty |
| GET | `/niche-radar` | Niche discovery (3 signal passes) | limit |
| GET | `/ideas` | AI-generated app ideas | sort_by, pattern_type, category, keyword, skip, limit |
| POST | `/ideas/generate` | Force regenerate all ideas | — |
| GET | `/dashboard/stats` | Aggregated stats (cached 5 min) | — |
| GET | `/dashboard/keyword-highlights` | Top enriched keywords by opportunity | limit |

**File:** `backend/app/api/routes.py:1782`

---

## Review Intelligence

| Method | Route | Purpose |
|---|---|---|
| GET | `/apps/{app_id}/review-intelligence` | Sentiment + feature analysis from reviews | force |
| GET | `/apps/{app_id}/autopsy` | "Why is this app winning" AI analysis | use_llm |

**File:** `backend/app/api/routes.py:2730`

---

## Growth Intelligence

| Method | Route | Purpose |
|---|---|---|
| GET | `/apps/{app_id}/metrics` | Time-series download + revenue snapshots | days |
| GET | `/apps/{app_id}/ads` | Ad creatives + campaigns for app | — |
| POST | `/apps/{app_id}/ads/scan` | Trigger ad intelligence scan | — |
| GET | `/ads` | All app ad intelligence (paginated) | skip, limit, network |
| GET | `/apps/{app_id}/growth-events` | Growth events for an app | — |
| GET | `/campaigns` | All growth events across all apps | event_type, active_only, min_confidence, skip, limit |

**File:** `backend/app/api/routes.py:2800+`

---

## Rankings & Categories

| Method | Route | Purpose |
|---|---|---|
| GET | `/rankings` | Ranking snapshots | app_id, chart_type, limit |
| GET | `/categories` | All categories | — |

---

## Search

| Method | Route | Purpose |
|---|---|---|
| GET | `/search/apps` | Search apps by keyword (iTunes + DB) | keyword, limit |

---

## Admin & Infrastructure

| Method | Route | Purpose |
|---|---|---|
| POST | `/admin/bootstrap` | One-shot pipeline for empty DB | — |
| GET | `/admin/bootstrap/status` | Check bootstrap state | — |
| GET | `/admin/discovery/metrics` | Discovery engine coverage metrics | — |
| POST | `/admin/discovery/run-charts` | Trigger chart discovery batch | batch_size |
| POST | `/admin/discovery/run-keywords` | Trigger keyword discovery | — |
| POST | `/admin/discovery/process-queue` | Process discovery queue | batch_size |
| POST | `/scrape/all` | Force re-scrape all tracked apps | — |
| GET | `/scheduler/status` | Scheduler jobs + next run times | — |
| POST | `/scheduler/jobs/{job_id}/trigger` | Immediately trigger a scheduled job | job_id path |

---

## Health

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | DB connectivity + scheduler state | — |
| GET | `/` | Service identity | — |

(These are on the root app, not the `/api/v1` router)

---

## Frontend ↔ Backend Mismatches

### Used by frontend but potentially missing / inconsistent:

| Frontend Call | Status | Notes |
|---|---|---|
| `getDownloadEstimate(appId)` | ✅ `/apps/{id}/download-estimate` | Implemented |
| `getCampaignTrackingList(params)` | ✅ `/campaigns` | Implemented |
| `getAdIntelligenceList(params)` | ✅ `/ads` | Implemented |
| `getBlowingUpApps(filters)` | ✅ `/apps/blowing-up` | Implemented |
| `getKeywordOpportunitiesForApp(id)` | ✅ `/apps/{id}/keywords/opportunities` | Implemented |
| `getAppAutopsy(id)` | ✅ `/apps/{id}/autopsy` | Implemented |
| Competitor page | ❌ | No backend endpoint |
| Alerts page | ❌ | No backend endpoint |
| Settings page | ❌ | No backend endpoint |

### Endpoints that exist but appear rarely used:
- `POST /keywords` — superseded by `GlobalKeywordSink`; rarely called directly
- `GET /rankings` — direct table dump; use `/apps/{id}/rank-history` instead
- `GET /apps/latest-60-days` — superseded by `/apps/latest?mode=new_releases`
- `GET /trending` (v1) — alias of `trending/v2`; frontend uses v2

---

*Documentation generated by auditing the current codebase. Last updated: 2026-03-17.*
