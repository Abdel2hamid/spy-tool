# Railway Deployment Guide

## Python Version

Railway must use **Python 3.11** (not 3.12 or 3.13).

`pydantic-core` (Pydantic v2's compiled Rust extension) does not have a
pre-built wheel for Python 3.13 at the pinned versions in `requirements.txt`.
Attempting to build from source fails on Railway's build infrastructure.

Railway's Nixpacks builder looks for version-pin files relative to the
**service root directory**. Since this service's root is set to `backend/`
in Railway settings, all Python version files must live inside `backend/`.

Three files are used (Nixpacks checks all of them):

| File | Content | Purpose |
|------|---------|---------|
| `backend/runtime.txt` | `python-3.11.9` | Heroku-style version pin |
| `backend/.python-version` | `3.11.9` | pyenv-style version pin |
| `backend/nixpacks.toml` | see below | Explicit Nix package + start command |

`backend/nixpacks.toml`:
```toml
[phases.setup]
nixPkgs = ["python311", "gcc"]

[start]
cmd = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

Do **not** rely solely on a `runtime.txt` at the repository root when the
Railway service root is `backend/` — Railway will not find it there.

---

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

### Backend service variables

Set these in **Railway → Backend Service → Variables**:

| Variable | Example | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql://user:pass@host:5432/db` | Provided automatically by Railway Postgres plugin |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Optional — only needed for AI Autopsy + Review Intelligence |
| `DEBUG` | `false` | Set to false in production |
| `MAX_TEST_APPS` | `0` | 0 = no cap (scrape all apps) |

The `DATABASE_URL` from Railway Postgres is in the format
`postgresql://...` — the app strips any `+asyncpg` suffix automatically,
so both formats work.

### Frontend service variables

Set these in **Railway → Frontend Service → Variables**:

| Variable | Example | Notes |
|----------|---------|-------|
| `BACKEND_URL` | `https://backend-production-xxxx.railway.app` | **Required** — no trailing slash, no `/api/v1` |

`BACKEND_URL` is a **server-side** env var read by `next.config.js` at runtime to
proxy `/api/*` requests to the backend. Do not prefix it with `NEXT_PUBLIC_`.

**Important:** The frontend browser code always calls relative URLs (`/api/v1/...`).
The Next.js server rewrites those to `$BACKEND_URL/api/v1/...` on the server side.
You do NOT need to set `NEXT_PUBLIC_API_URL` on Railway — leave it unset.

If you set `NEXT_PUBLIC_API_URL` on Railway, it must include the full path with
`/api/v1` (e.g. `https://backend-xxx.railway.app/api/v1`), otherwise all
endpoint calls will 404 because they append routes like `/dashboard/stats` to it.

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
