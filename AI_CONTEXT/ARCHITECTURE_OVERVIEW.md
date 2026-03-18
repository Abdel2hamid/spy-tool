# Architecture Overview

> AppStore Spy — AI-powered App Store Intelligence Platform

---

## System Overview

AppStore Spy is a self-hosted platform that continuously monitors the Apple App Store, mines competitive intelligence, and surfaces actionable opportunities for indie developers and ASO practitioners. It is designed as a free alternative to enterprise tools like Sensor Tower ($5K+/month).

**Stack:**
| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python 3.11+) |
| ORM | SQLAlchemy (sync sessions) |
| Database | PostgreSQL |
| Task Scheduler | APScheduler (AsyncIOScheduler) |
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind CSS |
| Charts | Recharts |
| Data Sources | iTunes API, App Store HTML/JS, Apple MZSearchHints autocomplete API |

**Deployment target:** Railway (backend + frontend + PostgreSQL as separate services)

---

## Core Components

### Backend Structure
```
backend/app/
├── main.py                   — FastAPI app, lifespan, DB migrations (_MIGRATIONS list)
├── api/routes.py             — ALL API routes in a single file (~2800 lines)
├── config.py                 — Pydantic Settings (reads .env)
├── database.py               — SQLAlchemy engine + SessionLocal + get_db
├── models/
│   ├── models.py             — All SQLAlchemy ORM models (20+ tables)
│   └── schemas.py            — All Pydantic request/response schemas
├── workers/
│   ├── scheduler.py          — APScheduler setup; registers 20+ recurring jobs
│   ├── tasks.py              — ScraperWorker + ScoringWorker + run_* wrappers
│   └── discovery_engine.py   — DiscoveryEngine (chart + keyword + developer expansion)
├── scrapers/
│   ├── app_details.py        — AppStoreAppScraper (iTunes Lookup API + RSS reviews + version HTML)
│   └── appstore.py           — AppStoreScraper (iTunes Search + iTunes RSS top charts)
├── services/                 — 35 service modules (listed in CODEBASE_MAP.md)
├── scoring/
│   ├── engine.py             — ScoringEngine (trending, opportunities, fresh risers, market weakness)
│   ├── feature_gaps.py       — FeatureGapAnalyzer (NLP on negative reviews)
│   ├── idea_generator.py     — IdeaGenerator (AI opportunity card generation)
│   ├── ai_potential.py       — AI integration potential scoring
│   └── weights.py            — Scoring weight constants
└── config/
    ├── scoring_config.py     — All scoring thresholds + algorithm parameters
    ├── rank_curves.py        — Category-aware rank-to-daily-download bands (8 bands × 9 categories)
    ├── category_arpu_profiles.py — Revenue ARPU profiles per App Store category
    └── calibration_profiles.py   — Per-category calibration multipliers for estimation
```

### Frontend Structure
```
frontend/src/
├── app/                      — Next.js App Router pages (17 routes)
│   ├── page.tsx              — Dashboard (home): stats, trending widget, opportunity-of-day
│   ├── apps/page.tsx         — App catalog with full filter/sort system
│   ├── apps/[id]/page.tsx    — App detail page (9 tabs: overview, ranking, reviews, analytics,
│   │                           keywords, market weakness, ads, growth events, autopsy)
│   ├── trending/page.tsx     — Trending apps (precomputed scores)
│   ├── blowing-up/page.tsx   — Apps Blowing Up (momentum detection)
│   ├── latest-apps/page.tsx  — Latest releases (3 tabs: new releases, fresh risers, released today)
│   ├── keywords/page.tsx     — Keyword intelligence explorer
│   ├── opportunities/page.tsx — Market opportunities list
│   ├── niche-radar/page.tsx  — Niche radar (3 signal passes)
│   ├── ideas/page.tsx        — AI-generated app ideas
│   ├── campaigns/page.tsx    — Campaign tracking (growth events)
│   ├── ads/page.tsx          — Ad intelligence browser
│   ├── discover/page.tsx     — App discovery search (import by URL/ID/name)
│   ├── rankings/page.tsx     — Rankings browser
│   ├── competitors/page.tsx  — Competitor analysis (UI stub — no backend)
│   ├── alerts/page.tsx       — Alerts (UI stub — no backend)
│   └── settings/page.tsx     — Settings (UI stub — no backend)
├── components/               — AppShell, ErrorBoundary, TrendingAppCard, sidebar, etc.
└── lib/
    ├── api.ts                — Typed API client (~1500 lines); all fetch calls live here
    ├── estimate-format.ts    — Shared formatters: fmtNum, fmtRev, fmtRange, confidenceLabel
    └── utils.ts              — cn() (tailwind-merge helper)
```

---

## Data Architecture

### Database Tables (25 total)

**Core entities:**
| Table | Purpose |
|---|---|
| `apps` | Primary entity — every tracked iOS app |
| `categories` | App Store categories (linked to apps) |
| `rankings` | Time-series rank snapshots (app × chart × date) |
| `reviews` | Individual app reviews from iTunes RSS |
| `app_versions` | Version history scraped from App Store HTML |
| `app_analytics` | Computed review growth, sentiment roll-ups |

**Keyword intelligence (7 tables):**
| Table | Purpose |
|---|---|
| `keywords` | Keyword dictionary + enrichment signals + quality scores |
| `keyword_metrics` | Normalized 1:1 metrics (search_volume, difficulty, trend_score) |
| `keyword_trends` | Weekly Google Trends time-series (sparklines) |
| `app_keywords` | App ↔ keyword relationship + rank + traffic score |
| `app_keyword_intelligence` | Per-app keywords extracted from title/subtitle/description |
| `app_discovered_keywords` | Keywords found via autocomplete + affix expansion |
| `keyword_search_snapshots` | Point-in-time App Store search result captures |
| `keyword_queue` | Decouples discovery from enrichment |

**Opportunity & intelligence:**
| Table | Purpose |
|---|---|
| `opportunities` | Computed market opportunities per app |
| `app_ideas` | AI-generated app idea cards (feature_gap / weak_market / keyword_gap) |
| `feature_gaps` | Feature requests extracted from negative reviews |
| `app_market_weakness` | Per-country negative review ratio analysis |
| `daily_reports` | Precomputed daily opportunity-of-day |

**Growth intelligence:**
| Table | Purpose |
|---|---|
| `app_trending_scores` | Precomputed trending scores, refreshed every 10 min |
| `app_blowing_up_scores` | Precomputed momentum scores, refreshed every 15 min |
| `app_metric_snapshots` | Time-series download + revenue estimate snapshots |
| `ad_creatives` | Individual ad creative records per app per network |
| `ad_campaigns` | Campaign-level aggregation per (app, network) |
| `growth_events` | Classified growth signal events (paid_push, organic_breakout, etc.) |

**Infrastructure:**
| Table | Purpose |
|---|---|
| `discovery_queue` | App Store IDs awaiting full scrape |
| `discovery_progress` | Tracks which chart/keyword/developer sources have been crawled |

---

## Intelligence Systems

### 1. Trending Engine
- Multi-window ranking momentum: 3d, 7d, 14d (weighted blend)
- Consistency bonus for sustained movers; absolute rank bonus for top-50 positions
- Review momentum: normalized new reviews/day
- Confidence penalty: penalizes apps with sparse ranking history
- **Storage:** `app_trending_scores` — precomputed every 10 min
- **File:** `services/trending_compute_service.py`

### 2. Blowing Up Engine
- 6 component scores: rank_velocity, rank_change, reviews_velocity, chart_presence, cross_market, consistency
- Human-readable badges: "Rapid Climb", "Fast Reviews", "Cross-Market", etc.
- Confidence score based on data completeness
- **Storage:** `app_blowing_up_scores` — precomputed every 15 min
- **File:** `services/blowing_up_service.py`

### 3. Download Estimation (4-Layer Ensemble)
- **L1 Rank Curve:** Category-aware rank → daily downloads (8 bands × 9 categories; `config/rank_curves.py`)
- **L2 Review Velocity:** reviews/day × install-to-review ratio × calibration
- **L3 Keyword Visibility:** keyword_count × avg_opportunity_score → footprint → daily estimate
- **L4 Momentum Adjustment:** ±20–30% multiplicative adjustment from trending data
- Dynamic weight rebalancing when signals are missing
- Confidence engine: Bayesian product of 5 factors (history, completeness, freshness, category reliability, review coverage)
- Anti-manipulation floor (10 dl/day) and cap (10× category average)
- **File:** `services/download_estimator.py`, `services/confidence_engine.py`

### 4. Revenue Estimation
- ARPU-based, per-category profiles (subscription vs IAP vs ad-driven)
- Monetization model hints detected from app metadata + price
- Range: low/medium/high ARPU × active installs × conversion rates
- **File:** `services/revenue_estimator.py`, `config/category_arpu_profiles.py`

### 5. Keyword Intelligence Pipeline
- Phase 1: Google Trends (trend_score, trend_growth, trend_velocity) — may be blocked on Railway
- Phase 2: Apple iTunes signals (apps_count, dominance_score)
- Phase 3: Opportunity (0-100) + feasibility (0-100) scoring
- Quality engine: quality_score + quality_tier (A/B/C) + canonical dedup
- **File:** `services/keyword_intelligence_pipeline.py`, `services/keyword_quality_engine.py`

### 6. Growth Intelligence Layer
- **Ad Intelligence:** Detects Apple Search Ads signals (rank + reviews correlation); optional Meta Ads Library integration (`FACEBOOK_ACCESS_TOKEN` required)
- **Campaign Tracking:** Classifies `growth_events` as paid_push / organic_breakout / mixed / momentum_surge / campaign_cooling / unknown_unusual
- **Metric Snapshots:** Download + revenue snapshots written to `app_metric_snapshots` on every scoring cycle
- **Files:** `services/ad_intelligence_service.py`, `services/campaign_tracking_service.py`, `services/metric_snapshot_service.py`

---

## Module Interactions

```
                    ┌─────────────────────────────────────────────────────┐
                    │              SCHEDULER (APScheduler)                │
                    │  20+ jobs: discovery, scrape, score, estimate, etc. │
                    └──────────────────────┬──────────────────────────────┘
                                           │
          ┌────────────────────────────────┼────────────────────────────────┐
          ▼                                ▼                                ▼
  DiscoveryEngine              ScraperWorker                    ScoringWorker
  (discovery_engine.py)        (tasks.py)                       (tasks.py)
        │                           │                                │
  charts × genres × 20 ctrs   iTunes Lookup API              ┌──────┴──────┐
  keyword search               iTunes RSS reviews             │             │
  developer expansion          App Store HTML                 ▼             ▼
        │                           │                   TrendingCompute  BlowingUpService
        ▼                           ▼                   DownloadEstimator RevEstimator
  discovery_queue  ──────▶  apps + rankings              MetricSnapshotService
                             + reviews + versions         AdIntelligenceService
                                                          CampaignTrackingService
                                                          KeywordIntelligencePipeline
                                                          IdeaGenerator
                                                          FeatureGapAnalyzer
                                                          MarketWeaknessCompute
                                    │
                                    ▼
                              FastAPI routes (api/routes.py)
                                    │
                                    ▼
                          Next.js frontend (api.ts → pages)
```

---

## What Is Implemented Today

| Feature | Status | Notes |
|---|---|---|
| App metadata scraping | ✅ | iTunes Lookup API |
| Review ingestion | ✅ | iTunes RSS; sentiment tagging |
| Top charts ingestion | ✅ | iTunes RSS JSON feed; 20 countries |
| Trending score computation | ✅ | Precomputed every 10 min |
| Blowing Up scores | ✅ | Precomputed every 15 min |
| Download estimation (4-layer) | ✅ | `download_estimator.py` |
| Revenue estimation | ✅ | `revenue_estimator.py` |
| Confidence engine | ✅ | `confidence_engine.py` |
| Keyword extraction from metadata | ✅ | `keyword_extraction_service.py` |
| Keyword discovery (autocomplete) | ✅ | `keyword_discovery_service.py` |
| Keyword intelligence pipeline | ✅ | Google Trends + Apple signals |
| Keyword rank tracking | ✅ | Via Playwright (may not run on Railway) |
| Market weakness analysis | ✅ | Per-country negative review ratio |
| Feature gap analysis | ✅ | Text pattern matching on reviews |
| Review sentiment tagging | ✅ | Rule-based, column on `reviews` table |
| AI opportunity idea generation | ✅ | `idea_generator.py` |
| Ad intelligence (Apple Search Ads) | ✅ | Heuristic (no real API access) |
| Ad intelligence (Meta Ads Library) | ⚠️ | Requires `FACEBOOK_ACCESS_TOKEN` |
| Campaign tracking | ✅ | `campaign_tracking_service.py` |
| App import / lookup | ✅ | `/apps/import` + `/apps/lookup/{id}` |
| Discovery pipeline | ✅ | Chart + keyword + developer expansion |
| LLM autopsy (Claude Haiku) | ⚠️ | Requires `ANTHROPIC_API_KEY` |
| Google Trends enrichment | ⚠️ | Blocked on Railway IPs; set `GOOGLE_TRENDS_ENABLED=false` |
| Competitor comparison page | ❌ | Frontend stub only |
| Alerts system | ❌ | Frontend stub only |
| Settings page | ❌ | Frontend stub only |
| DataForSEO integration | ❌ | Config flag only |

---

## Known Gaps

1. **No authentication** — the API is fully open; any caller can read/write everything
2. **routes.py is a monolith** — 2800 lines; should be split into domain routers
3. **Google Trends blocked on Railway** — returns empty DataFrame from cloud IPs; `GOOGLE_TRENDS_ENABLED=false` to skip
4. **Playwright keyword tracker** — depends on browser automation; not deployable on Railway without extra setup
5. **`install_estimator.py` and `download_estimator.py` both exist** — legacy (L1 only) vs. new (4-layer); both are active; `MetricSnapshotService` uses the new one
6. **No Alembic** — schema evolution via `_MIGRATIONS` list in `main.py`; not reversible
7. **In-process cache** — `_DASHBOARD_CACHE` is lost on restart; not distributed
8. **Competitors, Alerts, Settings** — three frontend pages are fully stubbed with no backend implementation

---

*Documentation generated by auditing the current codebase. Last updated: 2026-03-17.*
