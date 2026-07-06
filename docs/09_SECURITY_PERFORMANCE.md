# 09 — Security & Performance Review

**Scope:** RankSpy backend (FastAPI + PostgreSQL, single-instance on Railway).
**Branch:** `audit-fixes`.
**Method:** Direct source review — every claim below is grounded in code paths, not assumptions.

This document is written jointly from a **Security Engineer** and **Performance Engineer**
perspective. It records the security fixes already applied on this branch, the issues that
remain open, the current performance characteristics, and the structural limits that gate
scale.

---

## 1. Security Review

### 1.1 Authentication model

| Aspect | Implementation | File |
|---|---|---|
| Token type | JWT, HS256, `python-jose` | `services/auth_service.py` |
| Claims | `sub` (user id), `workspace_id`, `iat`, `exp`, `jti`, `iss="rankspy"` | `create_access_token()` |
| Validation | `require_exp` + `require_sub` enforced; `iss` checked when present | `decode_access_token()` |
| Expiry | 480 min (8 h) normal; 1 h for impersonation tokens | `create_access_token()` |
| Password hash | bcrypt cost 12, called directly (passlib deliberately avoided) | `hash_password()` |
| Password policy | 8–72 chars, upper+lower+digit, common-password blocklist | `auth_router._validate_password()` |
| User enumeration | Login runs bcrypt against a dummy hash when the user is absent (timing-flattened); resend-verification always returns success | `login_user()`, `resend_verification()` |

The secret is enforced: `config.py` raises `RuntimeError` at import time if `JWT_SECRET`
is unset in production (`RAILWAY_ENVIRONMENT`/`PRODUCTION`), and falls back to an ephemeral
per-process secret only in dev.

**Note on `jti`:** every token carries a unique `jti`, but it is **not persisted or checked**,
so it provides no revocation or replay protection today — it is forward-plumbing only.

### 1.2 Middleware auth gate (defense in depth)

`_AuthGateMiddleware` (`main.py`) now **cryptographically validates** the Bearer token
(`decode_access_token(...) is None → 401`) for every `/api/v1/*` request except an explicit
allowlist:

- Prefixes: `/api/v1/auth/`, `/api/v1/stripe/webhook`, `/api/v1/stripe/config`, `/api/v1/admin-console/announcements/active`
- Exact: `/`, `/health`, `/api/v1/categories`

This is a safety net; each endpoint still declares its own `Depends(...)`. The middleware
is added **after** `CORSMiddleware` and re-emits CORS headers on its own 401s so browser
error handling still works.

### 1.3 Tenant / workspace isolation — ✅ enforced via membership join

Isolation is **not** taken on trust from the token's `workspace_id`. `get_auth_context()`
(`api/deps.py`) resolves identity with a single query that **joins through `Membership`**:

```
User ⟕ Membership(user_id==User.id AND workspace_id==token.workspace_id)
     ⟕ Workspace(id==token.workspace_id)
     ⟕ Subscription(workspace_id==token.workspace_id)   [outer]
WHERE User.id==token.sub AND User.is_active
```

If the caller forges a `workspace_id` they are not a member of, the inner join yields no row
and the request is rejected with 401. This means a token cannot be used to read or mutate a
workspace the user does not belong to. ✅

### 1.4 Admin surface — ✅ fails closed

- `get_superadmin()` (`api/deps.py`) requires a valid token **and** `user.is_superadmin`,
  else 403. No implicit trust.
- `ADMIN_TOKEN` for the `X-Admin-Token`-gated endpoints: `config.py` auto-generates a random
  token in production if unset (endpoints stay reachable-proof but locked) and **disables**
  them in dev. `/run-migrations` compares with `secrets.compare_digest` and returns 403 when
  the token is missing or mismatched — **fails closed**. ✅
- Impersonation tokens are scoped (1 h TTL, `imp` claim carrying the impersonator id) and
  refuse to target another superadmin.

### 1.5 Stripe webhook — ✅ verified and off-loaded

`stripe_router.stripe_webhook()` reads the raw body, calls
`stripe_service.construct_event()` which **requires** `STRIPE_WEBHOOK_SECRET` and verifies
the `Stripe-Signature`; any failure → 400. The synchronous handler dispatch runs via
`run_in_threadpool` so blocking Stripe/DB I/O never sits on the event loop. ✅

### 1.6 What is FIXED on this branch

- ✅ **JWT is now validated in middleware** (previously only checked for header presence).
- ✅ **`/run-migrations` is admin-gated** (`compare_digest`, fails closed).
- ✅ **Admin dependencies fail closed** (`get_superadmin`, `ADMIN_TOKEN` handling).
- ✅ **Per-user rate limiting** keyed on `X-Forwarded-For` first hop, not the proxy IP.
- ✅ **Error internals no longer leaked** — the global exception handler logs the real
  exception and returns a fixed `{"detail": "Internal server error"}`.
- ✅ **Stripe webhook signature verified + handler off-loaded** to a threadpool.
- ✅ **`_NoOpEnforcer`** now applies free-plan limits to unauthenticated callers instead of
  granting unlimited access.
- ✅ **JWT secret fails fast in production**; admin token auto-locks.

### 1.7 OPEN issues

#### 🔴 O-1 — Usage-counter increment is not atomic (race condition)
- **Current impl:** `PlanEnforcer.increment()` (`plan_enforcement.py`) does a read-modify-write:
  `current = getattr(usage, action, 0); setattr(usage, action, current + 1); db.commit()`.
  `check()` and `increment()` are separate calls (or `check_and_increment` back-to-back), with
  no row lock, no `UPDATE ... SET x = x + 1`, and no unique-guarded upsert on
  `(workspace_id, month)`.
- **Why it's a problem:** Concurrent requests for the same workspace interleave their
  read-modify-write and lose increments, letting a workspace exceed its plan cap
  (metered-billing / abuse leakage). `_get_or_create_usage()` can also race two inserts of the
  same `(workspace_id, month)` row.
- **Fix:** Replace with an atomic SQL increment (`UPDATE workspace_usage SET {action} = {action} + 1 ...`)
  or `INSERT ... ON CONFLICT (workspace_id, month) DO UPDATE SET {action} = workspace_usage.{action} + 1`,
  and enforce the limit in the same statement (`WHERE {action} < :limit`, act on `rowcount`).
  Add a unique constraint on `(workspace_id, month)`.
- **Severity:** 🔴 High (revenue / quota integrity).

#### 🟡 O-2 — JWT stored in browser `localStorage` (XSS token theft surface)
- **Current impl:** The API returns `access_token` in the JSON login/register body; the SPA
  persists it client-side (localStorage-style bearer flow, not an `HttpOnly` cookie).
- **Why it's a problem:** Any XSS anywhere in the frontend can exfiltrate a long-lived (8 h)
  bearer token; there is no `jti` revocation to contain a leak.
- **Fix:** Move to `HttpOnly`, `Secure`, `SameSite` cookies for the access token (or a short
  access token + refresh rotation), and/or shorten TTL and wire `jti` into a revocation
  check. Keep a strict CSP.
- **Severity:** 🟡 Medium (depends on XSS existing; impact is full account takeover).

#### 🟡 O-3 — Email-verification token is replayable and delivered via GET
- **Current impl:** `create_email_verification_token()` mints a 60-min JWT (`purpose=email_verify`);
  `GET /auth/verify-email?token=...` decodes it and sets `email_verified=True`
  (`email_service.py`, `auth_router.verify_email`). The token is not single-use — nothing marks
  it consumed — so it works repeatedly for the full hour.
- **Why it's a problem:** The token lands in URLs (browser history, referrer headers, proxy/mail
  logs) and can be replayed within the window. Low blast radius (only flips a verified flag) but
  it is a reusable credential in a GET.
- **Fix:** Make it single-use — store a token id / hash on the user and invalidate on first use,
  or bump a `verification_token_version`. Prefer a POST confirm step over a GET side-effect.
- **Severity:** 🟡 Medium-Low.

#### 🟡 O-4 — No rate limit on data endpoints; `X-Forwarded-For` is spoofable
- **Current impl:** `rate_limit(...)` is applied only to auth-sensitive endpoints
  (`/auth/register` 3/60s, `/auth/login` 5/60s, `/auth/password`, `/auth/resend-verification`).
  The bulk of `/api/v1/*` data and admin endpoints have **no** limiter. The limiter keys on the
  **first** `X-Forwarded-For` hop (`rate_limiter.py`), which is client-supplied.
- **Why it's a problem:** Expensive endpoints (ILIKE search, scoring reads, CSV exports) are
  unthrottled — brute-force / scraping / DoS surface. Because XFF's first token is attacker-set,
  a client can rotate it to evade limits, or forge a victim's IP to exhaust the victim's window.
  The limiter is also per-process in-memory, so it does not hold across replicas.
- **Fix:** Trust only the proxy-appended hop (take the *right-most* XFF entry from the known
  Railway/edge proxy, or `X-Real-IP` set by the trusted layer). Add coarse per-workspace limits
  on heavy read/export endpoints. For multi-instance, back the limiter with Redis.
- **Severity:** 🟡 Medium.

#### 🔴 O-5 — No DB-level cascade on `apps.id` children; user delete orphans data **including live Stripe subscriptions**
- **Current impl:** `Membership`, `Subscription`, `WorkspaceUsage`, `Favorite`, `MyApp`, etc.
  declare `ondelete="CASCADE"` at the DB level, and `User.memberships` /
  `Workspace.subscription` use ORM `cascade="all, delete-orphan"`. **But** the high-volume
  `apps` children (`Ranking`, `Review`, `AppKeyword`, `Opportunity`, `AppVersion`, …) rely on
  **ORM-only** cascade with `lazy="noload"` and carry **no `ondelete` on the FK**
  (`app_id = Column(Integer, ForeignKey("apps.id"))`). Admin `delete_user()` / bulk delete do
  `db.delete(user)` and never touch Stripe.
- **Why it's a problem:**
  1. Deleting a user cascades their memberships but the **workspace + subscription are not
     deleted** (no user→workspace ownership FK), leaving an orphaned workspace and, critically,
     a **Stripe subscription that keeps billing** — no `stripe.Subscription.delete()` is called
     on user/workspace deletion.
  2. A raw/SQL delete of an `App` would fail or orphan rows because the `apps.id` FKs have no
     DB cascade; correctness depends entirely on going through the ORM object.
- **Fix:** On user/workspace delete, cancel the Stripe subscription first
  (`handle_subscription_deleted` path or `stripe.Subscription.delete`), then delete the
  workspace. Add `ondelete="CASCADE"` (or `SET NULL`) to the `apps.id` FKs so DB integrity does
  not depend on ORM load path. Consider soft-delete for auditability.
- **Severity:** 🔴 High (ongoing charges to deleted accounts + dispute risk + orphan storage).

#### ✅ O-6 — SQL injection: none found
- ILIKE filters interpolate user input into the **value** only — `App.name.ilike(f"%{search}%")`
  binds a parameter; the `%{search}%` is a bound string, not concatenated SQL. Raw `text()`
  queries (`admin_console_router`, `scheduler` country query) use bound params or static SQL.
  No string-built SQL predicates observed. ✅ (This is a *performance* problem — see P-2 — not
  an injection one.)

#### ✅ O-7 — SSRF: low
- Outbound fetches target fixed hosts (`itunes.apple.com/lookup?id=<int ids from DB>`). IDs are
  integers from our own tables, not free-form user URLs. No user-controlled host/path. Low risk.

#### 🟡 O-8 — Secrets handling
- **Good:** admin UI masks sensitive keys on read (`_mask`), `compare_digest` for admin token,
  JWT secret fail-fast, webhook secret required.
- **Gap:** payment gateway secrets (`stripe_secret_key`, `stripe_webhook_secret`,
  `paypal_client_secret`) are writable via `PUT /admin-console/settings/payment` and stored in
  the `admin_settings` table **in plaintext** (only masked on the way *out*). A DB dump or
  read-access to that table exposes live keys.
- **Fix:** Keep provider secrets in the environment / a secrets manager only; if DB-stored,
  encrypt at rest (envelope encryption) and never mirror env secrets into the table.
- **Severity:** 🟡 Medium.

---

## 2. Performance Review

### 2.1 What's good ✅

| Area | Why it's fast | Evidence |
|---|---|---|
| Keyword scoring iteration | **Keyset pagination** `iter_batches_keyset()` (`WHERE id > last ORDER BY id LIMIT n`) keeps large-table sweeps O(n) instead of O(n²) OFFSET scans | `utils/batch_utils.py` |
| Opportunity scoring | `_build_scored_opportunities()` **bulk-prefetches** ~10 fixed queries (rankings, reviews, categories, gap counts/objects, intel, discovered kw, keyword difficulty) then scores fully in memory — constant query count regardless of candidate volume | `scoring/engine.py:483` |
| Trending / blowing-up | `get_top_trending_apps_v2()` + `compute_trend_score_from_prefetch()` batch 4 queries and score with **zero per-app queries**; batched `IN` chunks of 2000 | `scoring/engine.py:1344` |
| Term lookups | Primary-keyword resolution uses `Keyword.term.in_([...])` set lookups (index-usable) rather than per-term queries | `scoring/engine.py:640-684` |
| Precomputed read paths | Trending / blowing-up / opportunity / weekly are computed by scheduler jobs into dedicated score tables, so the user-facing endpoints are indexed table reads, not on-demand computation | `workers/scheduler.py` |
| Per-country charts | Chart rankings served from indexed `rankings` rows written by `country_charts`; SLA-weighted rotation bounds request cost per run | `workers/scheduler.py:472` |

### 2.2 Bottlenecks

| # | Bottleneck | Where | Severity | Fix |
|---|---|---|---|---|
| P-1 | **N+1 in admin/list endpoints.** `list_users` runs a per-row `WorkspaceUsage` query inside the loop; `list_workspaces` runs **4 queries per workspace** (owner membership, owner user, member count, subscription, usage); `export_workspaces_csv` repeats the same per-row; `get_top_trending_apps` (v1) does a per-app `App` fetch + `calculate_review_growth` + `calculate_rating_velocity` | `admin_console_router.py:445,978-999,928`; `scoring/engine.py:827` | 🟡 Med | Batch with joins / grouped aggregates keyed by `workspace_id` (one usage query `IN (...)`, one grouped `member_count`, one subscription query), mirroring the prefetch pattern already used in scoring. Prefer v2 trending everywhere |
| P-2 | **ILIKE `%term%` filters with no trigram GIN index.** App search filters `name/subtitle/developer/description/primary_category/secondary_category` with leading-wildcard ILIKE; keyword and snapshot search likewise | `api/routes.py:287-300,318,381-382,483-484,542-543,1659,3333` | 🔴 High | Add `pg_trgm` GIN indexes on the searched text columns (or a `tsvector` FTS column). Leading-`%` ILIKE cannot use a btree and forces sequential scans that grow with the apps table |
| P-3 | **Whole-table / whole-category loads in the non-prefetch path.** `normalize_within_category()` loads **all** apps in a category per call; `calculate_category_growth`, `calculate_review_growth`, `calculate_rating_velocity` each issue their own query; the legacy `compute_trend_score()` chain issues ~11 queries per app | `scoring/engine.py:1072,149,69,90,900-1176` | 🟡 Med | Route all callers through the `*_from_prefetch` / `_build_scored_opportunities` batch path; retire the per-app legacy methods for bulk jobs |
| P-4 | **Per-item session churn in queue/keyword jobs.** `keyword_discovery_daily` and `_phase1_daily` call `_run_in_thread_with_session(...)` **once per app**, creating and tearing down a Session (and pool checkout) for every app | `workers/scheduler.py:1111,1220` | 🟡 Med | Reuse one thread-owned session per batch (open once, process the batch, commit periodically, close) instead of per-app open/close |
| P-5 | **Fresh TCP/TLS connection per Apple request (no keep-alive).** Bulk backfill and scheduler use `urllib.request.urlopen(...)` per iTunes lookup — urllib pools nothing, so every request pays a new connection + TLS handshake | `admin_console_router.py:1296`; `workers/scheduler.py:618` | 🟡 Med | Use a pooled client (`requests.Session` / `httpx.Client` with keep-alive, or async `httpx`) so connections are reused across the batch |
| P-6 | **Sync ORM inside `async` routes / handlers.** Endpoints are defined `def` (FastAPI threadpools them, which is fine), but async paths that do sync DB work must be off-loaded. The Stripe webhook was fixed (`run_in_threadpool`); scheduler jobs correctly use `asyncio.to_thread` / thread-owned sessions | `stripe_router.py:137`; `workers/scheduler.py` | 🟢 Low | Keep the invariant: never call a sync Session from a coroutine without `to_thread`/`run_in_threadpool`. No active violation found post-fix |

---

## 3. Scalability Review

The system runs as effectively **one process** (API + scheduler) against **one Postgres** with
**one egress IP**. These are the structural limits.

| # | Risk | Detail | Rating | How it scales |
|---|---|---|---|---|
| S-1 | **Single-instance, in-process scheduler** | APScheduler (`AsyncIOScheduler`) runs *inside* the API process. `main.py` gates it with `ENABLE_SCHEDULER` precisely because the scheduler holds in-process state — **two replicas both running it means duplicate scraping, duplicate writes, and racing queue claims**. So today you cannot horizontally scale the API without an explicit "API-only" replica split, and the scheduler itself is a single point of failure | 🔴 High | Extract a **dedicated worker service** (separate deploy) owning all jobs; run N stateless API replicas with `ENABLE_SCHEDULER=0`. Use a DB-backed job store / distributed lock so a worker restart doesn't lose or double-fire jobs |
| S-2 | **Single egress IP is the real acquisition throughput ceiling** | Every scrape/lookup/review/keyword-rank request exits one IP. The code already throttles around this: `review_scraper` caps at 300 US + 40×≤4 intl apps with an explicit comment *"request-heavy on a single egress IP … keep the scheduled sweep conservative … until a proxy pool is available"*; `country_charts` sleeps 0.5s between storefronts and batches 25; discovery jobs pace with `asyncio.sleep`. Coverage is SLA-rotated, not complete-per-cycle | 🔴 High | Introduce a **rotating proxy pool** for Apple-facing traffic; only then raise the per-run caps. Acquisition breadth (countries × genres × apps × reviews) is gated by this, not by CPU/DB |
| S-3 | **Unbounded rankings/reviews growth = the real storage & cost driver** | `rankings` gains rows every 2 h × apps × chart types × countries × genres; `reviews` ingests up to 500/app across storefronts. Only *keywords* have retention (`keyword_cleanup_daily`, `keyword_quality_pruning`). There is **no partitioning or retention on `rankings`/`reviews`** — they grow monotonically, inflating DB size (surfaced in `/admin-console/system` `pg_database_size`) and slowing every scan (compounds P-2/P-3) | 🔴 High | **Time-partition** `rankings` and `reviews` (monthly), add a retention/rollup policy (keep raw N days, aggregate older into daily snapshots — `AppMetricSnapshot` already exists), and archive cold partitions off the primary |
| S-4 | **Single DB pool shared by API + jobs vs Railway ~100-conn cap** | One engine: `pool_size=20`, `max_overflow=30` → **50 max connections**, shared between request handlers and ~30+ scheduler jobs (see `_JOB_TIMEOUTS`). The pool comment notes it "needs headroom for 32 jobs + API." A burst of concurrent heavy jobs plus API traffic can exhaust the pool (30 s `pool_timeout` then failures), and stacking multiple app instances multiplies toward Railway's ~100-connection ceiling | 🟡 Med | Separate pools once workers are split (worker service gets its own bounded pool; API gets its own). Add PgBouncer for connection multiplexing. Keep total `(pool_size+overflow) × replicas` safely under the server `max_connections` |
| S-5 | **In-memory, per-process rate limiter & job cursors** | `_SlidingWindowLimiter` and the resumable job cursors (`_kw_discovery_daily_cursor`, etc.) live in process memory — they reset on restart and are not shared across instances | 🟡 Med | Move rate-limit state to Redis and job cursors to a DB table so limits and resume points survive restarts and hold across replicas |

### Target topology

```
                 ┌──────────────┐        proxy pool (rotating egress)
   users ──────► │  API (N×)    │             │
                 │ SCHEDULER=0  │             ▼
                 └──────┬───────┘        ┌──────────────┐
                        │ own pool       │ Worker svc   │──► Apple / iTunes
                        ▼                │ (scheduler,  │
                 ┌──────────────┐        │  own pool)   │
                 │  PgBouncer   │◄───────┴──────────────┘
                 └──────┬───────┘
                        ▼
              Postgres (partitioned rankings/reviews + retention)
                        + Redis (rate limits, job cursors)
```

---

## Appendix — Severity legend

| Mark | Meaning |
|---|---|
| ✅ | Fixed / satisfactory as implemented |
| 🟢 | Low — monitor, no urgent action |
| 🟡 | Medium — schedule a fix |
| 🔴 | High — prioritize |
