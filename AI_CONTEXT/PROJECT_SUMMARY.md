# Project Summary

## What the Tool Does

AppStore Spy is a **self-hosted App Store market intelligence platform** that continuously monitors the iOS App Store to surface competitive insights, keyword ranking data, market weaknesses, and AI-generated app opportunity ideas.

It runs automated scrapers on a schedule, processes the raw data through analytics and NLP pipelines, scores opportunities, and presents everything through a modern Next.js dashboard.

## Who It Is For

| User Type | Primary Use Case |
|-----------|-----------------|
| Indie app developers | Find niches with low competition and high demand before building |
| ASO (App Store Optimization) specialists | Track keyword rankings and sponsored vs. organic placements |
| Mobile growth marketers | Monitor competitor review sentiment and acquisition gaps |
| Product managers | Extract feature requests from competitor reviews (feature gap mining) |
| App portfolio managers | Monitor multiple apps' health metrics from one dashboard |
| Growth hackers | Detect trending apps early and reverse-engineer their traction |

## What Problem It Solves

Enterprise App Store intelligence tools (Sensor Tower: $5,000+/month, AppTweak: $199–$999/month) are too expensive for indie developers and small studios. AppStore Spy provides equivalent core intelligence — keyword tracking, competitive analysis, sentiment mining, and AI-driven opportunity detection — as a self-hosted, free-to-run alternative.

**Core question answered:** "Which apps are winning, why are they winning, and what should I build next?" — without paying enterprise prices.

## Unique Positioning

AppStore Spy is the **only tool that automatically synthesizes competitive signals into actionable app ideas**. It mines competitor reviews for feature gaps, detects geographic market weaknesses, and generates scored startup/feature ideas with reasoning — a capability no commercial competitor offers.

## Tech Stack

- **Backend:** Python 3.9, FastAPI, SQLAlchemy (sync), PostgreSQL, APScheduler, Playwright
- **Frontend:** Next.js 14, TypeScript, Tailwind CSS, Recharts, Lucide icons
- **Scraping:** urllib + BeautifulSoup (metadata), Playwright Chromium (search results)
- **NLP:** Rule-based regex patterns + normalization maps (60+ entries)
- **Database:** PostgreSQL with 14 tables

## Deployment

- **Backend:** `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Frontend:** `next dev` or `next build && next start`
- **Database:** PostgreSQL at `localhost:5432/appstore_spy`
- Tables are auto-created on startup via `Base.metadata.create_all()`
