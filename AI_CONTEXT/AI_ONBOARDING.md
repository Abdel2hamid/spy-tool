# AI Onboarding — AppStore Spy

Quick-start guide for AI agents. Read this before touching code.

---

## What this project does

AppStore Spy is a self-hosted App Store intelligence platform. It:
1. **Discovers** iOS apps continuously (chart scraping, keyword search, developer expansion)
2. **Tracks** metadata, rankings, reviews, and version history for thousands of apps
3. **Scores** apps on trending momentum, "blowing up" signals, download/revenue estimates
4. **Surfaces** opportunities: weak market niches, keyword gaps, feature requests from reviews

Stack: FastAPI (Python) backend + Next.js 14 frontend + PostgreSQL + APScheduler

---

## Mandatory Working Rule

**Before touching any code**, read the existing `AI_CONTEXT/` docs:
1. `ARCHITECTURE_OVERVIEW.md` — system design + all intelligence systems
2. `API_ENDPOINTS.md` — every backend route with params
3. `DATABASE_SCHEMA.md` — all 25 tables with columns
4. `DATA_PIPELINE.md` — how data flows phase by phase
5. `CODEBASE_MAP.md` — file-level directory map

---

## 5-Minute Architecture

```
iTunes API + App Store HTML
        │
        ▼
DiscoveryEngine → discovery_queue → ScraperWorker → apps/rankings/reviews/versions tables
                                                              │
                                                              ▼
                                                     ScoringWorker
                                                       ├── TrendingComputeService → app_trending_scores
                                                       ├── BlowingUpService      → app_blowing_up_scores
                                                       ├── DownloadEstimator     → app_metric_snapshots
                                                       ├── KeywordPipeline       → keywords table
                                                       └── IdeaGenerator         → app_ideas table
                                                              │
                                                              ▼
                                                    FastAPI routes.py
                                                              │
                                                              ▼
                                                    Next.js frontend
```

**Scheduler cadence:** trending 10min, blowing-up 15min, scoring 1h, full scrape 6h, discovery 2h/6h/12h

---

## Where Core Logic Lives

| What | File |
|---|---|
| ALL API routes | `backend/app/api/routes.py` (2800 lines) |
| ALL DB models | `backend/app/models/models.py` |
| ALL Pydantic schemas | `backend/app/models/schemas.py` |
| ALL TypeScript types + API calls | `frontend/src/lib/api.ts` |
| App search + import | `backend/app/services/app_import_service.py` |
| Download estimation | `backend/app/services/download_estimator.py` |
| Revenue estimation | `backend/app/services/revenue_estimator.py` |
| Trending scores | `backend/app/services/trending_compute_service.py` |
| Blowing-up scores | `backend/app/services/blowing_up_service.py` |
| Scoring formulas | `backend/app/scoring/engine.py` |
| Scheduled jobs | `backend/app/workers/scheduler.py` |
| Scraping pipeline | `backend/app/workers/tasks.py` |
| DB migrations | `backend/app/main.py` → `_MIGRATIONS` list |
| Config thresholds | `backend/app/config/scoring_config.py` |

---

## How Frontend Connects to Backend

- API base URL: `NEXT_PUBLIC_API_URL` env var (default: `http://localhost:8000/api/v1`)
- All calls go through `frontend/src/lib/api.ts` — never fetch directly in components
- All pages use server component wrapper (`page.tsx`) + client component (`*Client.tsx`)
- All pages must be wrapped in `<AppShell>` from `components/AppShell.tsx`

Pattern:
```
frontend/src/app/my-page/page.tsx          → thin server wrapper
frontend/src/app/my-page/MyPageClient.tsx  → 'use client', fetches from api.ts, renders UI
```

---

## Key Conventions

### Adding a new endpoint
1. Route function in `routes.py`
2. Pydantic schema in `schemas.py`
3. TypeScript type + fetch function in `api.ts`
4. Test in `backend/tests/`

### Adding a new DB column / table
1. Add SQLAlchemy model in `models.py`
2. Add idempotent `ALTER TABLE` or `CREATE TABLE IF NOT EXISTS` SQL to `_MIGRATIONS` in `main.py`
3. Restart backend — migrations run automatically

### Schema evolution rule
- Never modify existing rows in `_MIGRATIONS`
- Always append new SQL at the bottom
- Each statement must be idempotent (use `IF NOT EXISTS`, `IF NOT EXISTS column`, etc.)

---

## Import / Search Architecture

The app has two search modes:

| Mode | Endpoint | Writes DB? | Purpose |
|---|---|---|---|
| Text search | `GET /apps/import?q=term` | No (for text) | Search local DB + iTunes; returns `source='database'` or `source='app_store'` |
| Direct lookup | `GET /apps/import?q={url or id}` | Yes | Detects URL/trackId, imports to DB, returns `direct_lookup=true` |
| Direct lookup (API) | `GET /apps/lookup/{track_id}` | Yes | Fetch by trackId from iTunes, import to DB, trigger enrichment |

**URL/ID detection:** `backend/app/utils/parse_appstore_query.py` — `parse_appstore_query(q)` returns `ParsedQuery(type, track_id)`. Handles:
- App Store URLs: `https://apps.apple.com/us/app/{name}/id{trackId}`
- iTunes URLs: `https://itunes.apple.com/us/app/id{trackId}`
- Numeric IDs: `718043190` (6–13 digits)
- ID-slug: `id718043190`
- Everything else → text

**Response shape:** `AppImportSearchResponse` has `direct_lookup: bool`, `error_hint: str | null`
- `direct_lookup=True, results=[{id>0}]` → frontend auto-navigates to `/apps/{id}`
- `direct_lookup=True, results=[], error_hint="..."` → Apple lookup failed; show error message
- `direct_lookup=False` → normal text search results

**Duplicate prevention:** `App.app_id` has `UNIQUE` constraint. `_get_or_create_app()` uses select-before-insert with rollback recovery (retries SELECT after unique violation to handle race conditions).

**Search component architecture** (3 files in `frontend/src/components/`):
- `SearchDropdown.tsx` — self-contained; holds all state + API calls; renders input + animated panel
- `SearchResultRow.tsx` — one result row; props: `app`, `isFocused`, `isImporting`, `onClick`, `onMouseEnter`
- `SearchSection.tsx` — section wrapper with `title` prop and `role="group"` for accessibility
- `Header.tsx` — thin shell; just `<SearchDropdown />` + mobile menu + notifications

**Keyboard navigation** (in `SearchDropdown`):
- `ArrowDown/Up` — moves `focusedIndex` through `[...localResults, ...storeResults]`
- `Enter` — triggers Open or Import for focused item
- `Escape` — calls `closeDropdown()` (clears query + blurs input)

**Dropdown animation** — always in DOM; `opacity-0 scale-95 pointer-events-none` → `opacity-100 scale-100 pointer-events-auto` via `transition-all duration-150 ease-out origin-top`

Frontend flow (`SearchDropdown.tsx`):
1. User types in header search → debounced `searchAppsImport(q)` call
2. If `res.error_hint` set → show error message in dropdown (e.g. "App not found...")
3. If `res.direct_lookup && results[0].id > 0` → auto-navigate to `/apps/{id}`
4. Local DB results (`source='database'`) → whole row is a `<Link>`; shows **"Open"** pill with `ExternalLink` icon
5. App Store results (`source='app_store'`) → shows **"Import"** button (indigo); clicking calls `lookupApp(track_id)` → writes to DB → redirect to `/apps/{id}`; shows "Importing…" + spinner while loading
6. Import failure → `importError` state shown below results in dropdown
7. `searchError` shown in dropdown when lookup/search fails

**Enrichment:** triggered via `background_tasks.add_task(service.trigger_enrichment, id)` only when `is_new=True`. Runs: keyword extraction → competitor mining → keyword intelligence pipeline.

---

## Where Tests Live

```
backend/tests/
├── test_import_search.py          36 tests — AppImportService search + lookup
├── test_download_estimator.py     70 tests — DownloadEstimator + ConfidenceEngine
├── test_growth_intelligence.py    41 tests — AdIntelligence + CampaignTracking
└── (more tests)
```

Run tests:
```bash
cd backend
python -m pytest tests/ -v
```

---

## Known Gotchas

1. **`routes.py` is 2800 lines** — use Ctrl+F / search. Route order matters for FastAPI (specific before generic).
2. **Google Trends blocked on Railway** — set `GOOGLE_TRENDS_ENABLED=false`. Keyword pipeline skips Phase A.
3. **`/apps/import` is read-only** — it never writes to DB. To actually import, call `/apps/lookup/{id}`.
4. **`_MIGRATIONS` never roll back** — append-only; idempotent SQL only.
5. **In-process cache** — `_DASHBOARD_CACHE` in routes.py is lost on restart.
6. **Dual download estimators** — `InstallEstimator` (legacy L1-only) and `DownloadEstimator` (new 4-layer). `MetricSnapshotService` uses the new one. Old `/apps/{id}/install-estimate` still uses the legacy one.
7. **Playwright keyword tracker** — `AppStoreSearchScraper` uses Playwright; may not run on Railway without extra Docker setup.
8. **iTunes genres are strings, not dicts** — `item.get("genres", [])` returns `["Productivity", "Business"]`, not objects.

---

## Quick Reference — Common Tasks

### Find how a feature works
1. Identify the frontend page (check `frontend/src/app/`)
2. Find the API call in `lib/api.ts`
3. Find the route in `routes.py`
4. Trace to the service/model

### Add a new intelligence signal
1. Add column(s) to a model in `models.py`
2. Add migration in `main.py`
3. Compute in a service in `services/`
4. Hook into `ScoringWorker.update_opportunities()` in `tasks.py`
5. Expose via endpoint in `routes.py`
6. Display in frontend

### Debug a 500 error
1. Check backend logs (FastAPI stdout)
2. Look at the route handler in `routes.py`
3. Check if DB migration ran (does the column/table exist?)
4. Check `_MIGRATIONS` for the relevant SQL

---

*Documentation generated by auditing the current codebase. Last updated: 2026-03-18.*
