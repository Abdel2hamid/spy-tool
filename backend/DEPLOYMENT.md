# Railway Deployment Guide

## Requirements Files

| File | When to use |
|------|-------------|
| `requirements.txt` | **Railway / production** — slim, fast build (~30 s) |
| `requirements-dev.txt` | **Local dev** — includes Playwright, numpy, scikit-learn, lxml |

Railway uses `requirements.txt` automatically. Do not point Railway at
`requirements-dev.txt` — it pulls in a 200 MB Playwright browser download
that fails on standard Railway instances.

---

## Railway Build Command

```
pip install -r requirements.txt
```

(Railway auto-detects this; no manual override needed.)

---

## Railway Start Command

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set this in **Railway → Service → Settings → Deploy → Start Command**.
`$PORT` is injected automatically by Railway.

---

## Required Environment Variables

Set these in **Railway → Service → Variables**:

| Variable | Example | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql://user:pass@host:5432/db` | Provided automatically by Railway Postgres plugin |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Optional — only needed for AI Autopsy + Review Intelligence |
| `DEBUG` | `false` | Set to false in production |
| `MAX_TEST_APPS` | `0` | 0 = no cap (scrape all apps) |

The `DATABASE_URL` from Railway Postgres is in the format
`postgresql://...` — the app strips any `+asyncpg` suffix automatically,
so both formats work.

---

## What Is NOT Installed in Production

These packages are intentionally excluded from `requirements.txt`:

| Package | Reason excluded |
|---------|----------------|
| `playwright` | 200 MB Chromium browser — only for keyword rank tracking |
| `numpy` | Was a dead import (not actually used) |
| `scikit-learn` | Not used anywhere in the codebase |
| `lxml` | Optional BeautifulSoup parser; stdlib `html.parser` works fine |
| `asyncpg` | App uses sync SQLAlchemy + psycopg2; asyncpg not needed |
| `alembic` | Only for local schema migrations, not needed at runtime |

### Functional impact

- **Keyword rank tracker** (Playwright-based App Store search scraping) will
  not run. The scheduler job will log a warning and skip gracefully.
- All other features — API, scoring, install/revenue estimates, niche radar,
  ideas, market weakness, feature gaps, review intelligence — work normally.

To enable keyword tracking on Railway, add a separate background worker
service with `requirements-dev.txt` + `playwright install chromium`.

---

## Local Development

```bash
# Install all packages including Playwright
pip install -r requirements-dev.txt

# Download Chromium browser for Playwright
playwright install chromium

# Start dev server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
