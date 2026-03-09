# AppStore Spy AI — Current Project State

## Goal
Build an **App Store Spy / Intelligence Tool** similar to:

- AppMagic
- SensorTower
- AppTweak

The tool discovers:

- Trending apps
- Keyword opportunities
- Weak competitors
- Emerging niches

---

# Tech Stack

Backend
- FastAPI
- Python 3.11
- SQLAlchemy
- APScheduler

Frontend
- Next.js
- React
- TypeScript
- Tailwind

Infrastructure
- Railway (Backend + Postgres)
- GitHub (source code)

---

# Current Deployment

Backend API → Railway  
Frontend Dashboard → Railway  
Database → PostgreSQL (Railway)

---

# Database Tables

apps  
keywords  
rankings  
reviews  
opportunities  
categories  
daily_reports  
feature_gaps  
app_keywords  
app_analytics  
app_versions  

---

# Keyword Intelligence Fields

Added to `keywords` table:

search_volume  
trend_score  
competition_score  
dominance_score  
opportunity_score  
feasibility_score  
growth_velocity  
trend_growth  
apple_popularity  
data_source  

Database migration already executed.

---

# Data Sources

Apple App Store  
→ app metadata  
→ rankings  
→ reviews

Google Trends (pytrends)  
→ keyword trend growth

DataForSEO (optional)  
→ search volume  
→ keyword difficulty

---

# Scraping Strategy

Priority:

1. Newly released apps
2. Apps launched in last 30 days
3. Trending apps
4. Ranking velocity apps

Older apps lower priority.

---

# Keyword Intelligence Pipeline

Pipeline:

1. discover keywords
2. fetch Google Trends
3. collect Apple signals
4. optional DataForSEO
5. compute scores
6. store in database

Scheduler jobs:

keyword_intelligence → every 12h  
keyword_scoring → every 6h  

---

# Ranking Intelligence

Track:

- top 50 apps per keyword
- ranking history
- ranking velocity
- new apps entering rankings

Ranking schema:

keyword_id  
app_id  
rank  
captured_at  

---

# Opportunity Logic

Opportunity detected when:

search_volume high  
competition_score low  
dominance_score low  
trend_growth positive  

Stored in:

opportunities table

---

# Important API Endpoints

Dashboard

GET /api/v1/dashboard/stats

Keywords

GET /keywords/enhanced  
GET /keywords/trending  
GET /keywords/{term}/detail  
POST /keywords/pipeline/run  

Ranking

GET /keywords/{id}/top-apps  
GET /keywords/{id}/ranking-history  
GET /apps/{id}/ranking-velocity  

Opportunities

GET /keywords/opportunities/high  

---

# Frontend Pages

Dashboard  
Apps  
Trending  
Opportunities  
AI Opportunities  
Niche Radar  
Keywords  
Rankings  

---

# System Goal

Detect automatically:

- trending keywords
- weak competition niches
- rising apps
- profitable app ideas

Build a **complete App Store Intelligence SaaS**.
