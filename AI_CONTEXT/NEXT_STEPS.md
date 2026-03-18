# Next Steps

Prioritized development roadmap. Items are ordered by impact vs. effort.
Current date: 2026-03-18.

---

## P0 — Immediately Valuable (days)

### 1. ✅ Upgrade Global App Search (URL/trackId import)
**What:** Header search box detects App Store URLs, track IDs, and numeric Apple IDs, then auto-imports and redirects.
**Files:** `backend/app/utils/parse_appstore_query.py` (new), `backend/app/api/routes.py` (modified `/apps/import`), `frontend/src/components/Header.tsx`
**Tests:** `backend/tests/test_parse_appstore_query.py` (24 tests)
**Status:** Complete.

### 2. Authentication
**What:** Add simple API key or JWT auth to protect the API.
**Why:** The API is fully open. Any caller can read or write everything.
**Files:** New middleware + `routes.py` dependency injection.
**Status:** Not started. No auth system exists.

---

## P1 — High Value (1–2 weeks)

### 3. Competitor Comparison Page
**What:** Side-by-side comparison of multiple apps on all key metrics.
**Why:** Frontend stub exists at `/competitors` — needs backend endpoint + data model.
**Files:** `frontend/src/app/competitors/page.tsx`, new backend endpoint, no new DB tables needed.

### 4. Alerts / Notification System
**What:** Push alerts when scores spike, an app releases a new version, or rank changes sharply.
**Why:** Converts the tool from passive dashboard to active monitor. Frontend stub exists at `/alerts`.
**Files:** New `notifications` table, `POST /notifications/webhook`, settings page wiring.

### 5. Settings Page
**What:** Persist user preferences: tracked apps, notification config, API tokens.
**Why:** Frontend stub exists at `/settings` — no backend wiring.
**Files:** `frontend/src/app/settings/page.tsx`, new settings endpoints.

### 6. Google Trends Alternative
**What:** Replace Google Trends (blocked on Railway) with Apple Search Ads popularity signals or DataForSEO.
**Why:** Keyword intelligence pipeline runs without trend data on Railway.
**Notes:** `GOOGLE_TRENDS_ENABLED=false` env var already skips the blocked phase. Need a replacement.

---

## P2 — Architecture (weeks)

### 7. Split `routes.py` into Domain Routers
**What:** Break the 2800-line monolith into `apps_router.py`, `keywords_router.py`, `intelligence_router.py`, `admin_router.py`.
**Why:** File is too large to navigate or reason about. Hot spot for merge conflicts.
**Risk:** High — changing route registration can break existing calls if not careful.

### 8. Alembic Migrations
**What:** Replace `_MIGRATIONS` list in `main.py` with proper Alembic migration history.
**Why:** `_MIGRATIONS` is append-only; cannot roll back; no version tracking.
**Status:** `backend/alembic/` directory exists but is not actively used.

### 9. Distributed Cache
**What:** Move `_DASHBOARD_CACHE` to Redis (or a DB table with TTL).
**Why:** In-process cache lost on restart; not distributed across multiple instances.

### 10. Data Retention Policy
**What:** Add cleanup jobs for `app_metric_snapshots` (keep 90d), old `reviews` (keep 1 year), etc.
**Why:** Tables grow forever. `app_metric_snapshots` currently has no retention limit.

---

## P3 — Long Term (months)

### 11. Real-Time Notifications
**What:** Webhook delivery when scores spike. WebSocket stream for live score updates.
**Why:** No push mechanism exists today. Dashboard refresh is manual.

### 12. Apple Search Ads API (Real)
**What:** Use Apple's Search Ads API (not heuristic) to get real keyword popularity and ad auction data.
**Why:** Current ad intelligence is heuristic-only. Apple SA requires app registration + OAuth.

### 13. Multi-Country Chart Coverage
**What:** Ensure all 20 country chart codes actually run on the discovery scheduler.
**Why:** Chart discovery supports 20 countries but coverage is not guaranteed.

### 14. Playwright on Railway
**What:** Make keyword rank tracker (Playwright-based) work on Railway.
**Why:** `AppStoreSearchScraper` requires a browser; Railway doesn't support it without a Docker layer.
**Option:** Use BrightData or ScrapingBee instead of Playwright.

### 15. Google Play Coverage
**Why:** Android market data would double the addressable use case. Major engineering effort.

### 16. Hosted SaaS Version
**Why:** Multi-tenant architecture, user accounts, Stripe billing. 3+ months of work.

---

## Technical Debt

| Item | File | Effort |
|---|---|---|
| routes.py monolith | `backend/app/api/routes.py` | 1 week |
| In-process dashboard cache | `backend/app/api/routes.py` `_DASHBOARD_CACHE` | 1 day |
| No Alembic | `backend/alembic/` | 2 days |
| No API auth | `backend/app/api/routes.py` | 1 week |
| Google Trends blocked | `backend/app/services/keyword_intelligence_pipeline.py` | need alternative |
| Playwright not deployable | `backend/app/scrapers/appstore_search_scraper.py` | need alternative |
| Dual estimators (legacy + new) | `install_estimator.py` vs `download_estimator.py` | remove legacy eventually |
| InstallEstimator legacy | `backend/app/services/install_estimator.py` | deprecate once confirmed stable |
| No data retention | `app_metric_snapshots`, `reviews` | 1 day |

---

*Documentation generated by auditing the current codebase. Last updated: 2026-03-18.*
