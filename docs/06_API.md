# RankSpy HTTP API Reference

> Branch: `audit-fixes` · Backend: FastAPI 0.109 (Python 3.11) · Source of truth: `backend/app/api/*.py` + `backend/app/main.py`
>
> This document is generated from a line-by-line read of the actual route
> handlers. Every endpoint below exists in code. Nothing here is aspirational.

---

## 1. Conventions

### 1.1 Base path & routers

All application endpoints are mounted under the **`/api/v1`** prefix
(`app.include_router(..., prefix="/api/v1")` in `main.py`). Four routers are
composed:

| Router | File | Router prefix | Mounted at | Endpoints |
|--------|------|---------------|------------|-----------|
| Auth | `api/auth_router.py` | `/auth` | `/api/v1/auth/*` | 8 |
| Main / data | `api/routes.py` | *(none)* | `/api/v1/*` | 111 |
| Admin console | `api/admin_console_router.py` | `/admin-console` | `/api/v1/admin-console/*` | 33 |
| Stripe | `api/stripe_router.py` | `/stripe` | `/api/v1/stripe/*` | 4 |

Three app-level (un-prefixed) endpoints live directly in `main.py`:
`GET /`, `GET /health`, and `GET /run-migrations` (also aliased at
`GET /api/v1/run-migrations`).

**Total documented: ~159 endpoints** (156 across the four routers + 3 app-level).

### 1.2 Authentication model

There are **two independent enforcement layers**. A request must satisfy both.

**Layer 1 — Global `_AuthGateMiddleware` (`main.py`).**
Added *after* CORS so its 401s still carry CORS headers. For every request whose
path starts with `/api/v1/`, it:

1. Skips `OPTIONS` (CORS preflight).
2. Skips explicitly public paths (see below).
3. Otherwise requires an `Authorization: Bearer <jwt>` header, and — new on this
   branch — **actually decodes and validates the JWT** via
   `decode_access_token()`. A missing header → `401 {"detail":"Not authenticated"}`;
   a malformed/expired token → `401 {"detail":"Invalid or expired token"}`.

The gate validates *signature + expiry only*. It does **not** check that the user
exists or is active — that is left to per-endpoint dependencies.

**Public allow-list** (bypass the gate):

```python
_PUBLIC_PREFIXES = (
    "/api/v1/auth/",                               # login, register, me, verify…
    "/api/v1/stripe/webhook",                      # Stripe-signed
    "/api/v1/stripe/config",                       # publishable key
    "/api/v1/admin-console/announcements/active",  # public banners
)
_PUBLIC_EXACT = { "/", "/health", "/api/v1/categories" }
```

**Layer 2 — Per-endpoint dependencies (`api/deps.py`).**

| Dependency | Guarantee | Used by |
|------------|-----------|---------|
| *(gate only)* | Valid JWT (any user) | Most public-catalog `GET`s that declare only `db` |
| `get_current_user` | Active `User` row resolved from `sub` | Mutations, background triggers |
| `get_auth_context` | `AuthContext(user, workspace, membership, subscription)` via one JOIN — workspace-scoped | Favorites, My Apps, Alerts, `/auth/me`, Stripe |
| `_bearer` + `PlanEnforcer.from_token(...)` | Plan gating (`check_premium`, `check_and_increment`) | Premium/AI/quota surfaces |
| `get_superadmin` | `User.is_superadmin == True` (403 otherwise) | All `/admin-console/*` |
| `_require_admin` (`X-Admin-Token` header, `secrets.compare_digest`, fails closed) | Shared ops secret | `/admin/*`, `/scrape/*`, `/scheduler/*`, `/run-migrations` |

> **Combined-gate nuance:** admin-token endpoints (e.g. `POST /api/v1/scrape/all`)
> are **not** in the public list, so they require **both** a valid JWT *and* the
> `X-Admin-Token`. The un-prefixed `GET /run-migrations` needs only the token;
> its `/api/v1/run-migrations` alias needs the token *and* a JWT.

> **Dead-fallback note:** endpoints that treat the bearer as optional
> (`PlanEnforcer.from_token` returns an "unknown/free" summary when no token is
> present — e.g. `GET /usage`) can never actually be reached tokenless, because
> the global gate rejects the request first.

### 1.3 Rate limiting

`app/utils/rate_limiter.py` — in-memory thread-safe sliding window keyed by
`(path, client_ip)`, IP taken from the first `X-Forwarded-For` hop (Railway/Next
proxy aware). Applied as `dependencies=[Depends(rate_limit(max, window_s))]`.
Exceeding the limit → **429** with `{"error":"rate_limit_exceeded","message":…,"retry_after_seconds":…}`.

| Limit | Endpoints |
|-------|-----------|
| 3 / 60s | `POST /auth/register` |
| 5 / 60s | `POST /auth/login`, `POST /auth/password` |
| 2 / 120s | `POST /auth/resend-verification` |
| 60 / 60s | `GET /rankspy/search`, `GET /search/apps` |
| 20 / 60s | `GET /apps/import` |
| 10 / 60s | `POST /apps/{id}/scrape-reviews`, `POST /apps/{id}/refresh` |

State is **per-process** (no Redis) — with multiple replicas the effective limit
multiplies by replica count.

### 1.4 Error & response shape

- Handled errors use FastAPI `HTTPException` → `{"detail": <string|object>}`.
- Unhandled exceptions hit the catch-all in `main.py`, which logs the real
  traceback and returns a CORS-safe **`500 {"detail":"Internal server error"}`**
  (never leaks internals).
- Many "browse" endpoints follow a **status-envelope** convention rather than
  HTTP errors: `{ "status": "success" | "insufficient_data" | "empty", "message", "required_signals", "items": [...] }`
  (e.g. `/trending`, `/trending/v2`, `/fresh-risers`, `/apps/blowing-up`,
  `/opportunity-of-day`, `/weekly-opportunities`, `/keyword-opportunities`).
- `GET /apps` and `GET /categories` **swallow exceptions and return an empty
  200 payload** — failures are logged but invisible to clients.

### 1.5 Pagination

Two coexisting styles (no single standard):

- **`skip` + `limit`** (offset-based), with a `total` in the body — favorites,
  my-apps, alerts, keywords, snapshots, ads, campaigns, `/apps` legacy path.
- **`page` + `limit`** (1-based) — `GET /apps` accepts both; `page` wins when
  `page > 1` (`effective_skip = (page-1)*limit`).
- **`offset` + `limit`** — `/apps/latest*`, `/rankspy/search`, `/alerts/events`.

Most list endpoints cap `limit` via `Query(..., le=N)` (typically 100–500);
a few (`GET /keywords`, `GET /opportunities`) take raw `int` params **with no
upper bound**.

---

## 2. Country-awareness summary

Country-aware storefront support was recently added. Legend: ✅ accepts a
`country`/storefront param · 🟡 core browse surface **not yet** country-aware
(should be) · 🔴 growth surface not country-aware.

**✅ Country-aware**

| Endpoint | Param(s) |
|----------|----------|
| `GET /countries` | `enabled_only` (lists storefronts) |
| `GET /chart-genres` | *(static genre list for selector)* |
| `GET /charts` | `country`, `chart_type`, `genre` |
| `GET /apps` | `country` (apps that chart in that storefront) |
| `GET /apps/blowing-up` | `country` (default `us`) |
| `GET /trending`, `GET /trending/v2` | `country` (default `us`) |
| `GET /apps/{id}/reviews` | `country` |
| `GET /apps/{id}/review-countries` | *(returns per-storefront counts)* |
| `POST /apps/{id}/scrape-reviews` | `country` (default `us`) |
| `POST /scrape/country-charts` | `country` (required) |
| `GET /keywords/{term}/detail`, `.../trend` | `country` |
| `POST /keyword-tracker/run`, `.../search` | `country` |
| `GET /keyword-search-snapshots` | `country` |
| `GET /apps/{id}/keyword-history`, `.../keywords` | `country` |

**🟡 / 🔴 NOT yet country-aware**

| Endpoint | Note |
|----------|------|
| `GET /fresh-risers` | 🟡 only `category_id`; US-implicit |
| `GET /apps/latest`, `/apps/latest-60-days` | 🟡 no storefront |
| `GET /niche-radar` | 🟡 global only |
| `GET /opportunity-of-day`, `/weekly-opportunities` | 🟡 no storefront |
| `GET /keyword-opportunities`, `/keywords/enhanced`, `/keywords/trending` | 🟡 no storefront |
| `GET /ideas` | 🟡 no storefront |
| `GET /rankings` | 🟡 no `country` filter (schema has one) |
| `GET /ads`, `GET /campaigns` | 🔴 global growth surfaces |

---

## 3. Endpoint catalog

Auth column: **public** · **user** (valid JWT via gate, no stronger dep) ·
**user✚** (`get_current_user`) · **ws** (`get_auth_context`, workspace-scoped) ·
**premium** (`PlanEnforcer.check_premium`) · **quota** (`check_and_increment`) ·
**superadmin** · **admin-token**.

### 3.1 Auth (`/api/v1/auth`, `auth_router.py`) — public prefix

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| POST | `/auth/register` | public · 3/60s | body `email, password, full_name, plan_code(starter\|pro)` | Create user+workspace+trial; sends verify email or returns Stripe checkout URL. Strong-password validation; allows retry of un-completed signups. |
| POST | `/auth/login` | public · 5/60s | body `email, password` | Verify credentials → JWT `AuthResponse`. 401 invalid, 403 email-unverified. |
| GET | `/auth/me` | ws | — | Current user + workspace + subscription info. |
| PATCH | `/auth/profile` | ws | body `full_name?, workspace_name?` | Update display/workspace name. |
| POST | `/auth/password` | ws · 5/60s | body `current_password, new_password` | Change password (validates current + strength). |
| GET | `/auth/verify-email` | public | `token` | Verify email from signed link. |
| POST | `/auth/resend-verification` | public · 2/120s | body `email` | Resend link (always 200 — no enumeration). |
| POST | `/auth/create-checkout-after-verify` | ws | — | Create Stripe checkout once email is verified. |

### 3.2 Apps & catalog (`routes.py`)

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| GET | `/apps` | user | `page/skip/limit`, `search`, `category`, `category_id`, `developer`, rating/reviews/rank ranges, `is_free`, `has_in_app_purchases`, date ranges, `fresh_only`, `ai_only`, `weak_market`, `min_feature_gaps`, download/revenue est. ranges, `confidence_label`, `sort_by/order`, **`country`** ✅ | Paginated, heavily-filterable app list (heavy TEXT/JSON columns deferred). |
| GET | `/apps/latest-60-days` | user | `limit, offset, category, sort_by/order` | Legacy: apps released/created in last 60 days. |
| GET | `/apps/latest` | user | `mode(new_releases\|released_today)`, `limit, offset, category, sort_by/order` | Release-based discovery; `released_today` = rolling 24 h. |
| GET | `/apps/{id}` | user | — | Single app by internal id. |
| POST | `/apps` | user✚ | body `AppCreate` | Insert an app row. |
| PATCH | `/apps/{id}` | user✚ | body `AppUpdate` | Partial update of an app. |
| GET | `/apps/{id}/detail` | user | — | App + last 20 versions + latest analytics. |
| GET | `/apps/{id}/developer-apps` | user | `limit` | Developer info + their other apps. |
| GET | `/apps/{id}/versions` | user | — | **All** version history (unbounded). |
| GET | `/rankspy/search` | user · 60/60s | `q(min 2)`, `limit, offset`, `force_live` | Unified search: local DB + live iTunes, dedup, auto-insert + async enrich. |
| GET | `/apps/import` | user · 20/60s | `q`, `limit` | Import search: text / App Store URL / trackId; URL/ID → direct lookup (quota `app_imports`). |
| GET | `/apps/lookup/{track_id}` | user (quota) | — | Full iTunes lookup + upsert; hydrates new imports (`app_imports`). |
| GET | `/search/apps` | user · 60/60s | `keyword(min 2)`, `limit` | iTunes search by keyword; inserts new apps + bg enrichment. |
| GET | `/categories` | **public** | — | List categories (id/name/slug). |
| GET | `/countries` | user | `enabled_only` | Storefronts for the selector (tier-ordered). ✅ |
| GET | `/chart-genres` | user | — | Static genre slugs for the top-charts selector. |

### 3.3 Charts / Rankings / Trending / Blowing-up / Fresh-risers

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| GET | `/charts` | user | `country`, `chart_type(topfree…)`, `genre`, `limit` ✅ | Top-chart leaderboard: latest rank per app for a (country, chart, genre). Raw SQL `DISTINCT ON`. |
| GET | `/rankings` | user | `app_id?, chart_type?, limit(le 500)` | Raw ranking rows, newest first. 🟡 no country. |
| GET | `/apps/{id}/rank-history` | user | `days(1–90)`, `chart_type?` | Rank time-series for one app. |
| GET | `/trending` | user | `limit(1–50)`, `category_id?`, **`country`** ✅ | Precomputed trending (status envelope); big brands filtered. |
| GET | `/trending/v2` | user | `limit`, `category_id?`, **`country`** ✅ | Enhanced trending (same precomputed source). |
| GET | `/apps/blowing-up` | user | `limit, skip, sort_by, sort_order, min_confidence, min_reviews_velocity, category?, chart_type?, timeframe`, **`country`**, `autocompute` ✅ | Momentum "blowing up" apps from precomputed table; brand-filtered; `autocompute` spawns a bg recompute. |
| GET | `/fresh-risers` | user | `mode(fresh_risers\|newest\|hidden_gems)`, `limit`, `category_id?` | 🟡 New releases with early traction (no country). |

### 3.4 Keywords / ASO (`routes.py`)

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| GET | `/keywords` | user | `skip, limit` *(unbounded)* | Raw keyword rows. |
| POST | `/keywords` | user✚ | body `KeywordCreate` | Insert one keyword via global sink. |
| GET | `/keywords/enhanced` | user | `search?, classification?, sort_by/order, skip, limit, min_volume, max_difficulty` | Scored keyword list; classification filter over-fetches ≤5000. |
| GET | `/keywords/trending` | user | `limit(1–100)` | Keywords with strongest rising trend signals. |
| GET | `/keywords/{term}/detail` | user | **`country`** ✅ | Competitors, ads presence, fragmentation, related terms. |
| GET | `/keywords/{term}/trend` | user | **`country`**, `days(7–90)` ✅ | Daily apps_count / avg_position / sponsored_ratio. |
| GET | `/dashboard/keyword-highlights` | user | `limit` | Top keywords by opportunity_score for dashboard. |
| GET | `/keyword-opportunities` | user | `min_difficulty, max_difficulty` | Global keyword opportunities (status envelope). |
| POST | `/keywords/pipeline/run` | user✚ | — | Fire full keyword-intelligence pipeline (bg asyncio task). |
| GET | `/keywords/pipeline/debug` | user | — | Enrichment coverage stats. |
| POST | `/keywords/discovery/run` | user✚ | — | Run keyword discovery engine (bg). |
| GET | `/keywords/discovery/status` | user | — | Discovery counts + last run. |
| GET | `/apps/{id}/aso-score` | user | — | ASO optimization score + tips. |
| GET | `/apps/{id}/keyword-suggestions` | user | — | Bucketed keyword suggestions. |
| GET | `/apps/{id}/keyword-intelligence` | user | — | Primary keyword, organic vs sponsored, traffic mix. |
| GET | `/apps/{id}/keywords/intelligence` | user | `refresh?` | Extracted keywords (metadata + iTunes); auto bg re-extract if stale. |
| POST | `/apps/{id}/keywords/intelligence/extract` | user✚ | — | Trigger metadata keyword extraction (bg). |
| GET | `/apps/{id}/keywords/discovered` | user | `limit(1–500)` | Autocomplete-discovered keywords for an app. |
| POST | `/apps/{id}/keywords/discover` | user✚ | — | Trigger per-app keyword discovery (bg); requires prior extraction. |
| POST | `/apps/{id}/keywords/discover-phase1` | user✚ | — | Phase-1 pipeline (alphabet+competitor+gap+scoring, bg). |
| GET | `/apps/{id}/keywords/opportunities` | user | `limit(1–200)` | Top per-app keyword opportunities. |
| GET | `/apps/{id}/keyword-history` | user | `keyword`, **`country`**, `days(7–365)` ✅ | Rank-over-time for one app+keyword. |
| GET | `/apps/{id}/keyword-history/keywords` | user | **`country`** ✅ | Keywords an app has appeared in (picker). |
| POST | `/keyword-tracker/run` | user✚ (quota) | **`country`**, `keyword_limit` ✅ | Scan tracked keywords in App Store search (`keyword_refreshes`). |
| POST | `/keyword-tracker/search` | user✚ | `keyword`, **`country`** ✅ | Scrape search results for one keyword. |
| GET | `/keyword-search-snapshots` | user | `keyword?, app_id?, is_sponsored?`, **`country`**, `skip, limit` ✅ | Filtered keyword-search snapshots. |
| GET | `/keyword-tracker/traffic-sources` | user | — | Organic-vs-ads mix across all apps. |

### 3.5 Opportunities / Ideas / Feature gaps

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| GET | `/opportunities` | user | `skip, limit` *(unbounded)*, `min_probability?` | Opportunity rows by success probability. |
| GET | `/opportunity-of-day` | user | — | Today's Opportunity of the Day (same-day cache). |
| GET | `/weekly-opportunities` | user | — | Top-5 opportunities this ISO week (cached). |
| GET | `/ideas` | user | `sort_by/order, pattern_type?, category?, keyword?, skip, limit` | Auto-generated app ideas. |
| POST | `/ideas/generate` | user✚ (quota) | — | Regenerate all ideas (`ai_requests`). |
| GET | `/apps/{id}/feature-gaps` | user | — | Feature gaps mined from reviews. |
| POST | `/apps/{id}/feature-gaps/analyze` | user✚ | — | Force re-run feature-gap analysis. |
| GET | `/apps/{id}/market-weakness` | user | — | Per-country negative-review analysis (computes on first call). |

### 3.6 Reviews (`routes.py`)

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| GET | `/apps/{id}/reviews` | user | `rating?`, **`country`**, `skip, limit` ✅ | Reviews for an app, filterable by storefront. |
| GET | `/apps/{id}/review-countries` | user | — | Storefronts with reviews + counts (selector). ✅ |
| POST | `/apps/{id}/scrape-reviews` | user✚ · 10/60s | **`country`** ✅ | On-demand review scrape for a storefront. |
| GET | `/apps/{id}/review-intelligence` | premium (quota) | `force?` | LLM-powered review analysis (`ai_requests`, `check_premium`). |
| GET | `/apps/{id}/autopsy` | premium (quota) | `use_llm?` | "Why is this app winning?" report; optional AI narrative. |

### 3.7 Analytics / Estimates / Metrics

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| GET | `/apps/{id}/analytics` | user | — | Latest computed analytics (404 if none). |
| GET | `/apps/{id}/install-estimate` | user | — | Install estimate (computes+persists on demand). |
| GET | `/apps/{id}/revenue-estimate` | user | — | Revenue estimate (on demand). |
| GET | `/apps/{id}/download-estimate` | user | — | 4-layer ensemble download + revenue estimate. |
| GET | `/apps/{id}/metrics` | user | `days(1–90)` | Latest metric snapshot + history + 7-day delta. |
| POST | `/apps/{id}/metrics/compute` | user✚ | — | On-demand metric-snapshot computation. |

### 3.8 Competitors (`routes.py`) — all premium

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| GET | `/competitors/compare` | premium | `app_ids` (2–5) | Side-by-side app comparison. |
| GET | `/competitors/rank-history` | premium | `app_ids` (2–5), `days(7–90)` | Rank overlay on shared date axis. |
| GET | `/competitors/keyword-gaps` | premium | `target_id`, `competitor_ids` (1–4) | Keywords competitors rank for that target doesn't. |

### 3.9 Ads / Campaigns / Growth — premium where noted

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| GET | `/apps/{id}/ads` | premium | — | Campaigns + creatives for one app. |
| POST | `/apps/{id}/ads/scan` | premium (user✚) | — | On-demand ad scan (Meta token from env). |
| GET | `/ads` | premium | `network?, active_only, skip, limit` | 🔴 Global apps-with-ads listing (batch-prefetched). |
| GET | `/apps/{id}/growth-events` | user | `active_only?` | Growth/campaign events for an app. |
| POST | `/apps/{id}/growth-events/detect` | user✚ | — | On-demand growth-signal detection. |
| GET | `/campaigns` | user | `event_type?, active_only, min_confidence, skip, limit` | 🔴 Global growth-event listing + blowing-up scores. |

### 3.10 Niche radar

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| GET | `/niche-radar` | premium | `limit(1–50)` | 🟡 Top emerging micro-niches (`check_premium`). |

### 3.11 Favorites / My-apps / Alerts (`routes.py`) — workspace-scoped

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| GET | `/favorites` | ws | `skip, limit` | Paginated favorited apps. |
| GET | `/favorites/ids` | ws | — | Bare favorited app-id list. |
| POST | `/favorites` | ws | body `{app_id}` | Add favorite (409 if dup). |
| DELETE | `/favorites/{app_id}` | ws | — | Remove favorite. |
| GET | `/my-apps` | ws | — | User's own apps + ASO scores. |
| GET | `/my-apps/ids` | ws | — | Bare my-app id list. |
| POST | `/my-apps` | ws | body `{app_id}` | Mark app as own. |
| DELETE | `/my-apps/{app_id}` | ws | — | Unmark. |
| POST | `/my-apps/{app_id}/refresh` | ws | — | Re-hydrate metadata (bg thread). |
| GET | `/alerts` | ws | — | Workspace alerts + unread counts (batched). |
| POST | `/alerts` | ws | body `AlertCreate` | Create alert rule (type-validated, max 50/ws). |
| PUT | `/alerts/{id}` | ws | body `AlertUpdate` | Update alert. |
| DELETE | `/alerts/{id}` | ws | — | Delete alert + events. |
| GET | `/alerts/events` | ws | `limit, offset, unread_only` | Triggered events. |
| GET | `/alerts/events/unread-count` | ws | — | Unread count. |
| POST | `/alerts/events/{event_id}/read` | ws | — | Mark one read. |
| POST | `/alerts/events/read-all` | ws | — | Mark all read. |
| GET | `/usage` | user | — | Current-month usage counters + plan limits. |

### 3.12 Billing / Stripe (`stripe_router.py`)

| Method | Path | Auth | Key params | Description |
|--------|------|------|-----------|-------------|
| GET | `/stripe/config` | **public** | — | Publishable key for the frontend. |
| POST | `/stripe/create-checkout` | ws | body `{plan_code}` | Create Checkout session URL. |
| POST | `/stripe/webhook` | **public** (Stripe-signed) | raw body + `Stripe-Signature` | Handle events (checkout/subscription/invoice/trial). Handlers run in threadpool. |
| POST | `/stripe/billing-portal` | ws | — | Customer Portal session URL. |

### 3.13 Admin console (`admin_console_router.py`) — all **superadmin**

Public exception: `GET /admin-console/announcements/active` (**public**).

| Method | Path | Key params | Description |
|--------|------|-----------|-------------|
| GET | `/admin-console/dashboard` | — | High-level platform stats. |
| GET | `/admin-console/users` | `search?, filter?, skip, limit` | List users + workspace/plan/usage. |
| POST | `/admin-console/users` | body `CreateUserRequest` | Admin-create user (no verify email). |
| PATCH | `/admin-console/users/{id}` | body | Update user fields. |
| DELETE | `/admin-console/users/{id}` | — | Delete user. |
| GET | `/admin-console/users/{id}/detail` | — | Full user drill-down. |
| POST | `/admin-console/users/{id}/reset-password` | body `{new_password}` | Reset a user's password. |
| POST | `/admin-console/users/{id}/impersonate` | — | Mint an impersonation JWT. |
| POST | `/admin-console/users/bulk` | body `{user_ids, action, plan_code?}` | Bulk deactivate/activate/delete/change-plan. |
| GET | `/admin-console/users/{id}/activity` | `skip, limit` | User activity log. |
| GET | `/admin-console/export/users` | — | CSV export of users (StreamingResponse). |
| GET | `/admin-console/export/workspaces` | — | CSV export of workspaces. |
| GET | `/admin-console/workspaces` | `search?, skip, limit` | List workspaces + owner/plan/usage. |
| PATCH | `/admin-console/subscriptions/{workspace_id}` | body | Edit a workspace subscription. |
| GET | `/admin-console/trials` | — | Trialing workspaces + days left. |
| POST | `/admin-console/trials/{workspace_id}/extend` | body | Extend a trial. |
| GET | `/admin-console/jobs` | — | Scheduled jobs + next run. |
| POST | `/admin-console/jobs/{job_id}/trigger` | — | Fire a scheduler job now. |
| GET | `/admin-console/job-metrics` | — | Scheduler job metrics. |
| POST | `/admin-console/apps/{app_id}/rescrape` | — | Force re-scrape one app. |
| POST | `/admin-console/apps/bulk-backfill` | body | Bulk backfill app metadata. |
| GET | `/admin-console/system` | — | DB size / table / queue health. |
| GET | `/admin-console/activity` | `skip, limit` | Admin activity log. |
| GET | `/admin-console/announcements` | — | List announcements. |
| POST | `/admin-console/announcements` | body `AnnouncementCreate` | Create announcement. |
| PATCH | `/admin-console/announcements/{id}` | body `AnnouncementUpdate` | Update announcement. |
| DELETE | `/admin-console/announcements/{id}` | — | Delete announcement. |
| GET | `/admin-console/announcements/active` | **public** | — | Active banners for all users. |
| POST | `/admin-console/promote/{user_id}` | — | Promote a user to superadmin. |
| GET | `/admin-console/settings/payment` | — | Masked payment settings. |
| PUT | `/admin-console/settings/payment` | body | Update payment settings. |
| GET | `/admin-console/settings/plans` | — | Plan config. |
| PUT | `/admin-console/settings/plans` | body | Update plan config. |

### 3.14 Ops / scrape triggers (`routes.py`) — **admin-token** (+ JWT via gate)

| Method | Path | Key params | Description |
|--------|------|-----------|-------------|
| POST | `/admin/bootstrap` | — | Full discovery→scrape→scoring pipeline (bg); 409 if running. |
| GET | `/admin/bootstrap/status` | — | Bootstrap + data-pipeline state. |
| POST | `/admin/bootstrap-data` | — | Build rankings from existing metadata + score (bg); 409 if running. |
| GET | `/admin/discovery/metrics` | — | Live discovery-engine metrics. |
| POST | `/admin/discovery/run-charts` | `batch_size(1–100)` | Run a chart-discovery batch. |
| POST | `/admin/discovery/run-keywords` | — | Run keyword discovery for all pending. |
| POST | `/admin/discovery/process-queue` | `batch_size(1–100)` | Process discovery queue (full scrape). |
| POST | `/scrape/all` | — | Scrape all tracked apps. |
| POST | `/scrape/country-charts` | `country` (required) ✅ | Scrape top charts (free+grossing, multi-genre) for a storefront. |
| POST | `/apps/{id}/refresh` | *(user✚ · 10/60s)* | Re-scrape one app (this is **user**, not admin-token). |
| GET | `/scheduler/status` | — | Scheduler + registered jobs. |
| POST | `/scheduler/jobs/{job_id}/trigger` | — | Trigger a scheduler job by id. |
| GET | `/ingestion/status` | *(user)* | Ingestion pipeline status (no admin token). |
| GET | `/dashboard/stats` | *(user✚)* | Dashboard counts (5-min TTL cache). |

### 3.15 App-level (`main.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | public | Name/version/status. |
| GET | `/health` | public | DB + scheduler + ranking-freshness + pool + jobs health. |
| GET | `/run-migrations` · `/api/v1/run-migrations` | admin-token | `alembic upgrade head` (the `/api/v1` alias also requires a JWT). |

---

## 4. Known API issues (from code)

Severity is engineering judgment based strictly on the code read.

### 4.1 N+1 query patterns — **Medium**

- `GET /admin-console/users` (`admin_console_router.py:445`) — inside the per-row
  loop it issues a **separate `WorkspaceUsage` query per user**. N+1 over the page.
- `GET /admin-console/workspaces` (`admin_console_router.py:977+`) — per workspace
  it queries owner membership, owner user, and member count individually. 3× N+1.
- `GET /my-apps` (`routes.py:4240`) — calls `ASOScoreService.score(app.id)` in a
  loop, one full ASO computation per app. Expensive, unbounded by page size
  (no `limit` param at all — returns *every* my-app).

> **Already fixed (batched):** `GET /ads`, `GET /campaigns`, `GET /alerts`,
> `GET /alerts/events` explicitly prefetch related rows in single `IN (...)`
> queries and comment out the N+1. `get_auth_context` uses one JOIN instead of
> four queries. Keep these as the pattern to copy.

### 4.2 Unbounded / over-fetching queries — **Low–Medium**

- `GET /keywords` and `GET /opportunities` take `skip`/`limit` as raw `int` with
  **no `le` cap** — a client can request an arbitrarily large page.
- `GET /my-apps` and `GET /apps/{id}/versions` return **all** rows (no limit).
- `GET /keywords/enhanced` with a `classification` filter runs `q.limit(5000)`
  then filters/paginates **in Python** — worst-case 5000-row materialization.
- Several browse endpoints over-fetch `limit * 4` (blowing-up, trending) or
  `limit * 2` (trending keywords) to compensate for brand filtering — acceptable
  but worth noting for large `limit`.

### 4.3 `async def` routes doing **sync ORM on the event loop** — **Medium**

FastAPI runs plain `def` routes in a threadpool but `async def` routes on the
loop. These `async` handlers call the **synchronous** SQLAlchemy `Session`
(and `PlanEnforcer`) directly before/around their awaited work, blocking the
loop for the duration of those queries:

- `POST /apps/{id}/keywords/intelligence/extract` (`routes.py:3107`)
- `POST /apps/{id}/keywords/discover` (`routes.py:3176`)
- `POST /apps/{id}/keywords/discover-phase1` (`routes.py:3561`)
- `POST /keyword-tracker/run` (`routes.py:3249`) — sync `PlanEnforcer` + then awaits
- `POST /keyword-tracker/search` (`routes.py:3284`)
- `POST /apps/{id}/ads/scan` (`routes.py:3770`) — sync `db.query` then `to_thread`
- `POST /apps/{id}/growth-events/detect` (`routes.py:3919`)
- `POST /apps/{id}/refresh`, `POST /scrape/*`, `/admin/discovery/*` — async + sync `db.query`

> **Good pattern already in place:** `stripe_webhook` wraps its sync handlers in
> `run_in_threadpool(...)` — the model the above should follow.

### 4.4 Duplicate route-function names — **Medium** (breaks OpenAPI client-gen)

Two pairs of handlers share a Python function name within `routes.py`:

- `trigger_keyword_discovery` — `POST /admin/discovery/run-keywords` (line 2863)
  **and** `POST /apps/{app_id}/keywords/discover` (line 3176).
- `get_keyword_opportunities` — `GET /keyword-opportunities` (line 1447)
  **and** `GET /apps/{app_id}/keywords/opportunities` (line 3614).

Both routes function at runtime (FastAPI registers by decorator), but FastAPI
derives `operationId` from the function name, so each pair produces **colliding
operationIds** in the OpenAPI schema — generated TypeScript/Python SDK clients
will clash or silently drop one. The later definition also shadows the earlier
as a module attribute. Rename one of each pair.

### 4.5 Error leakage — mostly fixed, some remaining — **Medium**

**Fixed:** the global `_unhandled_exception_handler` returns a generic
`500 "Internal server error"`; `/scrape/*`, `/apps/{id}/refresh`,
`/keyword-tracker/*` catch and re-raise generic 500s; `/run-migrations` returns
only the exception **type** name.

**Remaining leakage (raw exception string reaches the client):**

- `auth_router.py:307` (`POST /auth/register`) and `:514`
  (`POST /auth/create-checkout-after-verify`) raise
  `502 detail=f"Payment setup failed: {type(exc).__name__}: {exc}"` — leaks the
  underlying Stripe/DB exception text to unauthenticated callers.

### 4.6 Other reliability notes — **Low**

- `GET /apps` and `GET /categories` **swallow all exceptions** and return an
  empty `200` — a DB fault looks identical to "no results" to the client.
- The global auth gate validates JWT signature/expiry only; it does **not**
  verify the user still exists or is active. That check exists only where
  `get_current_user`/`get_auth_context` is declared — pure-`db` GET handlers
  will accept a valid-but-orphaned token until a stronger dep is added.
- Rate limiter is per-process/in-memory; effective limits scale with replica
  count and reset on restart.
