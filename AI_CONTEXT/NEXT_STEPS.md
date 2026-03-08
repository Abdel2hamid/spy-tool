# Next Steps

Prioritized development roadmap. Items are ordered by impact vs. effort.

---

## Priority 1 — Quick Wins (1–3 days each)

### 1. Keyword History Charts
**What:** Visualize how an app's rank position for a specific keyword changes over time.
**Why:** High analyst value. Data already exists in `keyword_search_snapshots` — only needs a new query + chart.
**Where:** Add to `KeywordIntelligenceTab` in `frontend/src/app/apps/[id]/page.tsx`
**Implementation:**
- Query: `SELECT DATE(captured_at) as date, MIN(position) as best_rank FROM keyword_search_snapshots WHERE app_id = ? AND keyword = ? GROUP BY DATE(captured_at) ORDER BY date`
- Add new API endpoint: `GET /apps/{id}/keyword-history?keyword=focus+timer`
- Add `KeywordHistoryChart` component (re-use existing `RankHistoryChart` pattern)

---

### 2. Delete `appstore_backup.py`
**What:** Remove the stale unused scraper file.
**Why:** Reduces confusion for future developers.
**File:** `backend/app/scrapers/appstore_backup.py`
**Risk:** None — file is not imported anywhere.

---

### 3. Version Change Detection
**What:** Detect when a tracked app publishes a new version and surface it as an alert.
**Why:** "Competitor shipped a major update" is a high-value signal.
**Implementation:**
- Compare `app_versions.version` strings on each scrape
- If new version detected, write a `notifications` table record
- Frontend: "Recent Updates" feed on Dashboard

---

### 4. Keyword Rank Tracker — Expand Results Per Keyword
**What:** Capture top 50 results per keyword instead of top 16.
**Why:** Apps ranked #17-50 are invisible in current data.
**Implementation:**
- Add scroll-based pagination in `AppStoreSearchScraper._scrape_once()`
- Scroll page, wait for new results to load, re-run `_EXTRACT_JS`
- Increase `MAX_RESULTS_PER_KEYWORD` to 50 in `keyword_rank_tracker.py`

---

## Priority 2 — High Impact Features (1–2 weeks each)

### 5. Install Estimation Model (v1)
**What:** Estimate monthly downloads per app using review velocity as a proxy.
**Why:** The single biggest feature gap vs. all competitors.
**Implementation:**
- Add `estimated_installs_monthly` FLOAT column to `apps` table
- Formula: `review_count_last_30d × category_install_to_review_ratio`
- Category ratios: games ~1000:1, productivity ~300:1, utilities ~200:1 (based on public Apple data points)
- Display in app overview tab with confidence band: "Estimated: 5K–15K/month"
- Compute in `ScoringWorker.update_opportunities()`

---

### 6. LLM-Powered Review Analysis
**What:** Replace rule-based feature gap NLP with Claude Haiku batch analysis.
**Why:** Dramatically improves feature extraction quality. Catches nuanced requests regex misses.
**Implementation:**
- Add `anthropic` SDK to requirements
- Batch 50-100 negative reviews per app per analysis run
- Prompt: "Extract: (1) unmet feature requests, (2) competitor comparisons, (3) pricing complaints. Return structured JSON."
- Add `llm_summary` TEXT column to `app_analytics` table
- Display LLM summary in Analytics tab

---

### 7. Apple Search Ads API Integration
**What:** Get real keyword popularity data from Apple's Search Ads API.
**Why:** Replaces the `search_volume = app_count × 850` estimate with real data.
**Implementation:**
- Register for Apple Search Ads API access
- Add `apple_popularity_score` INTEGER (0-5) to `keywords` table
- Fetch weekly via new scheduler job
- Update all scoring formulas to use Apple's data when available

---

### 8. Version Change Alerting (Full)
**What:** Email/webhook notifications when tracked apps release updates.
**Why:** Converts the tool from passive dashboard to active competitor monitor.
**Implementation:**
- Add `notifications` table: `(app_id, event_type, payload JSON, created_at, is_sent)`
- Event types: `new_version`, `rank_change`, `new_feature_gap`, `trending_spike`
- Add `POST /notifications/webhook` endpoint that delivers to configured URL
- Frontend settings page: configure webhook URL, notification types

---

### 9. Competitive Set Comparison
**What:** Side-by-side comparison of multiple apps on all key metrics.
**Why:** Users currently must navigate to each app individually.
**Implementation:**
- New frontend page: `/compare?ids=123,456,789`
- Comparison table: rating, reviews, rank, keyword count, feature gap count, update frequency
- Radar chart visualization (Recharts RadarChart) for quick visual comparison
- "Add to comparison" button on app detail page and app browser cards

---

## Priority 3 — Infrastructure (2–4 weeks each)

### 10. API Authentication
**What:** Add JWT-based authentication to all API endpoints.
**Why:** Required for any public deployment or multi-user setup.
**Implementation:**
- Add `users` table (id, email, hashed_password, api_key, plan_tier)
- FastAPI dependency: `get_current_user` validates Bearer token
- `/auth/login`, `/auth/register`, `/auth/refresh` endpoints
- All existing endpoints add `Depends(get_current_user)`

---

### 11. Alembic Migrations
**What:** Replace `create_all()` with proper database migrations.
**Why:** Current approach cannot alter existing tables — adding columns requires manual SQL.
**Implementation:**
- Initialize Alembic: `alembic init alembic`
- Create initial migration from current models
- All future model changes → generate migration: `alembic revision --autogenerate -m "add column"`
- Run: `alembic upgrade head`

---

### 12. Niche Radar — Automated Opportunity Feed
**What:** Daily digest of emerging App Store micro-niches from anomaly detection.
**Why:** The product's "killer differentiator." Proactive intelligence vs. reactive dashboard.
**Implementation:**
- Anomaly detector: z-score on `rank_velocity` and `review_growth` vs. category baseline
- Cluster semantically similar keywords (cosine similarity on term embeddings)
- Generate "niche brief" for each anomalous cluster
- New frontend widget: "This Week in App Niches" on Dashboard
- Optional: weekly email digest

---

### 13. Multi-Country Keyword Tracking
**What:** Run keyword rank tracker across US, UK, Germany, Australia, Canada.
**Why:** International ASO is a major use case. Many indie developers target global markets.
**Implementation:**
- Modify `keyword_rank_tracker.py` to accept country list
- Run `AppStoreSearchScraper` per country (5 countries × N keywords)
- `keyword_search_snapshots` already has `country` column — no schema change needed
- Frontend: country selector in Keywords tab

---

## Priority 4 — Long-Term (1–3 months each)

### 14. Revenue Estimation Model
Requires install estimates (Priority 2, item 5) to be built first.

### 15. "Winning App Autopsy" Reports
AI-generated narrative explanation of why an app is succeeding. Combines all data sources through an LLM.

### 16. Google Play Coverage
Android market data via Play Store scraping. Major engineering effort.

### 17. Hosted SaaS Version
Multi-tenant architecture with user accounts, per-user data isolation, Stripe billing.

---

## Technical Debt to Clear

| Item | File | Effort |
|------|------|--------|
| Delete unused backup scraper | `backend/app/scrapers/appstore_backup.py` | 5 min |
| Enable Alembic migrations | `backend/alembic/` | 2 days |
| Add API authentication | `backend/app/api/routes.py` + new auth module | 1 week |
| Fix settings page to actually persist | `frontend/src/app/settings/page.tsx` | 2 days |
| Add rate limiting to API | `backend/app/main.py` | 1 day |
| Add request logging/monitoring | `backend/app/main.py` | 1 day |
