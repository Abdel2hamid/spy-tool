# Session Memory

Template and log for future AI coding sessions. Each session summary should be appended below.

---

## How to Use This File

At the start of a new coding session, read this file to understand recent changes.
At the end of a session (or when asked to "remember"), append a new entry using the template below.

---

## Session Entry Template

```
---

## Session: YYYY-MM-DD

**Summary:** One sentence description of what was accomplished.

**Changes Made:**
- Brief description of each change

**Files Modified:**
- `path/to/file.py` — what changed
- `path/to/file.tsx` — what changed

**Files Created:**
- `path/to/new_file.py` — what it does

**Features Added:**
- Feature name: how it works

**Bugs Fixed:**
- Bug description: how it was fixed

**Next Tasks:**
- What to do next session

**Notes / Gotchas:**
- Anything important to remember about this session's changes
```

---

## Session Log

---

## Session: 2026-03-08 (Session 1 — Project Kickoff & Core Features)

**Summary:** Built the entire AppStore Spy tool from scratch — backend scraping, scoring engine, all API routes, and Next.js frontend.

**Features Added:**
- App discovery via iTunes Search API and top charts RSS feeds
- Full app metadata scraping (iTunes Lookup API)
- Version history scraping from App Store HTML with JSON extraction
- Review collection from iTunes RSS API (paginated)
- Chart rankings with rank velocity computation
- `ScoringEngine` with 7 composite metrics
- Market weakness analysis (per-country negative review ratios)
- Feature gap NLP mining (regex trigger patterns + synonym normalization)
- AI app idea generator (3 patterns: feature_gap, weak_market, keyword_gap)
- APScheduler with 5 recurring jobs
- 30+ FastAPI endpoints
- Next.js 14 frontend: Dashboard, Apps browser, App detail (8 tabs), Trending, Opportunities, AI Ideas, Keywords, Rankings pages
- Advanced app filtering system (19 parameters)

**Files Created (key files):**
- `backend/app/main.py` — FastAPI app + lifespan
- `backend/app/models/models.py` — 14 SQLAlchemy models
- `backend/app/models/schemas.py` — Pydantic schemas
- `backend/app/api/routes.py` — All API endpoints
- `backend/app/scrapers/appstore.py` — iTunes search + charts
- `backend/app/scrapers/app_details.py` — Full app scraper
- `backend/app/scoring/engine.py` — Scoring engine
- `backend/app/scoring/feature_gaps.py` — NLP analyzer
- `backend/app/scoring/idea_generator.py` — AI idea generator
- `backend/app/workers/tasks.py` — ScraperWorker + ScoringWorker
- `backend/app/workers/scheduler.py` — APScheduler jobs
- `frontend/src/app/apps/[id]/page.tsx` — App detail (8 tabs, ~1250 lines)
- `frontend/src/lib/api.ts` — All TypeScript types + API functions

---

## Session: 2026-03-08 (Session 2 — Version History Fix)

**Summary:** Fixed version history scraping after Apple migrated to Svelte-rendered pages.

**Bugs Fixed:**
- Version history showed only 1 version (current): Apple changed page rendering — the `?see-all=versions` URL returns 404, and CSS class `.version-history__item` no longer exists.

**Fix Applied:**
- `backend/app/scrapers/app_details.py:get_app_versions()`:
  - Now fetches the main app page URL (not `?see-all=versions`)
  - Searches all `<script>` tags for embedded JSON containing `"mostRecentVersion"`
  - Uses recursive `_find_key()` helper to navigate the JSON tree
  - Path: `mostRecentVersion → seeAllAction → pageData → shelves[0] → items`
  - Each item: `primarySubtitle` = version, `secondarySubtitle` = date, `text` = release notes
  - Date parsing handles format: `"Thu Mar 05 2026 10:54:19 GMT+0000 (...)"`
  - BeautifulSoup CSS fallback kept but likely broken on current pages

**Key Gotcha:** Apple's App Store pages embed version data in a `<script>` tag as JSON, not in the HTML DOM. The JSON structure changes periodically. The recursive `_find_key()` approach is more resilient than hard-coded path navigation.

---

## Session: 2026-03-08 (Session 3 — Real App Store Search Scraping)

**Summary:** Implemented complete Playwright-based keyword rank tracking system with sponsored detection and keyword intelligence.

**Features Added:**
1. **Keyword Rank Tracker** (`backend/app/jobs/keyword_rank_tracker.py`): Scrapes live App Store search results using Playwright. Saves to `keyword_search_snapshots` table. Updates `AppKeyword.position` for tracked apps.
2. **AppStoreSearchScraper** (`backend/app/scrapers/appstore_search_scraper.py`): Playwright Chromium browser scraper. Sponsored detection via DOM inspection. Icon URLs enriched via iTunes batch lookup after extraction.
3. **KeywordIntelligenceService** (`backend/app/services/keyword_intelligence.py`): Scores per-app keyword intelligence from snapshots. Computes primary_keyword, confidence, organic/ad keyword lists, traffic mix.
4. **New DB table:** `keyword_search_snapshots` (14 columns, multiple indexes)
5. **New API endpoints:** 5 new endpoints under `/keyword-tracker/` prefix
6. **Frontend: Keywords tab** added as 8th tab on app detail page with traffic mix bar, keyword tables, manual scan input

**Critical Bug Fixed:**
- App Store search URL: `?term=productivity` → 404 (broke in early 2026). Fixed to `?q=productivity`.

**Key Gotcha:** Apple's App Store search images are lazy-loaded with `loading="lazy"` and no `srcset` or `data-src`. Headless Playwright cannot trigger lazy loading. Solution: After extracting app IDs, do a separate batch iTunes Lookup API call to get `artworkUrl100`.

**Files Modified:**
- `backend/app/models/models.py` — Added `KeywordSearchSnapshot`
- `backend/app/models/schemas.py` — Added 8 new schemas
- `backend/app/workers/scheduler.py` — Added `job_keyword_rank_tracker`
- `backend/app/api/routes.py` — Added 5 new endpoints
- `frontend/src/lib/api.ts` — Added `KeywordIntelligence` types + 2 functions
- `frontend/src/app/apps/[id]/page.tsx` — Added `KeywordIntelligenceTab` component (8th tab)

**Files Created:**
- `backend/app/scrapers/appstore_search_scraper.py`
- `backend/app/jobs/__init__.py`
- `backend/app/jobs/keyword_rank_tracker.py`
- `backend/app/services/__init__.py`
- `backend/app/services/keyword_intelligence.py`

---

## Session: 2026-03-08 (Session 4 — AI Context Memory System)

**Summary:** Created `AI_CONTEXT/` folder with 11 comprehensive documentation files for future AI session context.

**Files Created:**
- `AI_CONTEXT/PROJECT_SUMMARY.md`
- `AI_CONTEXT/ARCHITECTURE_OVERVIEW.md`
- `AI_CONTEXT/FEATURES_INDEX.md`
- `AI_CONTEXT/CODEBASE_MAP.md`
- `AI_CONTEXT/DATA_PIPELINE.md`
- `AI_CONTEXT/SCRAPERS_INDEX.md`
- `AI_CONTEXT/API_ENDPOINTS.md`
- `AI_CONTEXT/DATABASE_SCHEMA.md`
- `AI_CONTEXT/KNOWN_LIMITATIONS.md`
- `AI_CONTEXT/NEXT_STEPS.md`
- `AI_CONTEXT/SESSION_MEMORY.md` (this file)

Also created: `PRODUCT_STRATEGY_REPORT.md` at repository root (product strategy analysis).

---
