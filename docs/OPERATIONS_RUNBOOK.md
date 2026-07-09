# RankSpy — Operations Runbook

> Deploy, rollback, backup/restore, and monitoring procedures for production on Railway.
> Pairs with the [Production Launch Plan](../RankSpy_Production_Launch_Plan.pdf) and the [Production Stability Report](./04_CTO_REVIEW.md).

---

## 0. Environment variables (production checklist)

Set these on the Railway **backend** service before first deploy. Missing `JWT_SECRET` in production is a hard boot failure by design.

| Var | Required | Notes |
|---|:--:|---|
| `DATABASE_URL` | ✅ | Railway Postgres connection string |
| `JWT_SECRET` | ✅ | long random secret; **app refuses to boot without it in prod** |
| `ADMIN_TOKEN` | ✅ | superadmin / ops-endpoint token (fails closed if unset) |
| `CORS_ORIGINS` | ✅ | comma-separated frontend origin(s) |
| `ENABLE_SCHEDULER` | ✅ | `1` on **exactly one** instance; `0` on any extra replica |
| `PAYMENT_PROVIDER` | ✅ | `stripe` today; `airwallex` after Phase 2b |
| `FRONTEND_URL` | ✅ | used for checkout success/cancel + portal return URLs |
| `SENTRY_DSN` | ⚠️ | enables error monitoring (no-op if unset) — set before launch |
| `SENTRY_TRACES_SAMPLE_RATE` | ⛔ | optional, default `0.0` |
| Payment keys | ✅ | Stripe: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`. Airwallex (Phase 2b): client id / api key / webhook secret |
| `ANTHROPIC_API_KEY` | ⚠️ | review intelligence + app autopsy |
| `RESEND_API_KEY` | ⚠️ | transactional email |
| `DEBUG` | ⛔ | leave unset/false in prod — `true` re-enables public `/docs` |

Frontend service: `BACKEND_URL` (proxy target) and, once wired, `NEXT_PUBLIC_SENTRY_DSN`.

---

## 1. Deploy procedure

```
1. Ensure CI is green on the PR (backend pytest + frontend build).
2. Take a manual DB snapshot (see §3) — ALWAYS before a deploy that includes a migration.
3. Merge PR → Railway auto-deploys the backend.
4. Watch backend deploy logs for:
   - "Running upgrade …" lines (Alembic 0001→N) applying cleanly
   - "Scheduler started — N recurring jobs registered"
   - no exception/tracebacks during lifespan startup
5. Hit GET /health → expect { db: ok, scheduler: running, jobs: N }.
6. Run the smoke tests (§5).
7. Confirm Sentry is receiving events (trigger a harmless test error if needed).
```

**Migrations run automatically at boot** (`alembic upgrade head` in the FastAPI lifespan). A failing migration raises during startup and the instance will **crash-loop** — that is intentional (never serve on a half-migrated schema), but it means a bad migration = outage until rolled back. Always snapshot first.

---

## 2. Rollback procedure

**Rule of thumb:** roll back *code* first (fast, safe). Only touch the *schema* if the new migration is the problem, and prefer **restore-from-snapshot** over `alembic downgrade` (downgrades that drop columns are data-lossy).

### 2a. Code-only rollback (no migration in the bad deploy)
```
1. Railway → backend service → Deployments → select the last-known-good deploy → "Redeploy".
   (or: git revert the merge commit, push → auto-deploy)
2. Verify GET /health and smoke tests (§5).
```

### 2b. Bad migration rollback
The new revision's DDL is additive/idempotent, but a bad data migration or an incompatible schema change needs care:
```
Option A — forward-fix (preferred if the schema change is fine but code is bad):
   → code-only rollback (2a); the newer schema is backward-compatible with the
     older code for our additive migrations (0002–0006 only ADD columns/tables).

Option B — restore from snapshot (if the schema itself is bad / data corrupted):
   1. Put the backend in maintenance (scale to 0 or ENABLE_SCHEDULER=0 + stop traffic).
   2. Restore the pre-deploy snapshot (§3) into the Postgres instance.
   3. Redeploy the last-known-good code.
   4. Verify §5.

Avoid `alembic downgrade` on production data unless the downgrade is known
non-destructive — our downgrades DROP columns/indexes and will lose data.
```

**Compatibility note:** migrations `0002`→`0006` are all additive (new columns/tables/indexes, backfilled). That means **old code runs safely against the new schema**, so 2a (code rollback) is almost always the right move and needs no DB action.

---

## 3. Backups & restore (recovery readiness)

> **Must be verified before launch (Blocker).** Do a real test restore at least once.

```
Verify Railway backups:
  1. Railway → Postgres plugin → Backups. Confirm automated backups / PITR are ON.
  2. Note the retention window and restore granularity.

Manual snapshot (before every migration deploy):
  - Railway dashboard "Backup now", OR
  - pg_dump:  pg_dump "$DATABASE_URL" -Fc -f rankspy_$(date +%Y%m%d_%H%M).dump

Test restore (do once, on STAGING, before launch):
  1. Create a scratch Postgres.
  2. pg_restore --clean --no-owner -d "$SCRATCH_URL" rankspy_*.dump
  3. Point a staging backend at it, run smoke tests (§5).
  4. Record the time-to-restore. If you can't restore, you have no backups.
```

---

## 4. Monitoring

| Signal | Where | Alert on |
|---|---|---|
| App errors / exceptions | Sentry (backend + frontend) | any new unhandled error; error-rate spike |
| Job health | `GET /health` `jobs` block + logs `[SCHEDULER]` | any job `fail`/`timeout` count rising |
| Apple blocking | logs (403 circuit breaker) | 403-storm / breaker open |
| Migration failure | deploy logs (startup) | crash-loop on boot |
| DB pool | `GET /health` pool telemetry | checked-out near pool_size |
| Webhook failures | logs + Sentry | payment webhook 4xx/5xx |

Recommended alerts (Sentry + Railway/uptime): **job-failure, 403-storm, migration-failure, 5xx-rate, webhook-failure.**

### Frontend Sentry — wiring steps (do at launch)
The backend Sentry is already wired (set `SENTRY_DSN`). For the Next.js frontend:
```
1. cd frontend && npm i @sentry/nextjs
2. npx @sentry/wizard@latest -i nextjs   (generates sentry.client/server.config + instrumentation)
   — or add the config files manually per Sentry's Next.js guide.
3. Set NEXT_PUBLIC_SENTRY_DSN in the Railway frontend service.
4. Redeploy; trigger a client error and confirm it lands in Sentry.
```
(Intentionally not committed yet — it pulls a package and codegen that must land in one deliberate change so `next build` stays green.)

---

## 5. Smoke tests (run on staging, then again on prod after cutover)

```
[ ] GET /health → db ok, scheduler running, jobs registered
[ ] Register → email verify link works → login → JWT accepted
[ ] GET /apps loads (data OR honest empty state — never a 500)
[ ] Top Charts / Trending / Blowing-Up / app detail load per country
[ ] Reviews tab loads; storefront selector works
[ ] Billing: create-checkout returns a URL; complete a sandbox payment;
    webhook flips subscription → active; plan gate enforces a limit
[ ] Hit a usage limit deliberately → 402 blocks (verifies atomic counter)
[ ] Password reset end-to-end
[ ] /api/v1/* rejects missing/invalid JWT; admin endpoints reject missing X-Admin-Token
[ ] /docs is NOT publicly reachable (prod)
[ ] Security headers present (curl -I): HSTS, X-Frame-Options, X-Content-Type-Options, CSP
[ ] Exactly ONE instance has ENABLE_SCHEDULER=1
```

---

## 6. Incident quick reference

| Symptom | First action |
|---|---|
| Site 500s after deploy | Code rollback (2a); check Sentry for the exception |
| Boot crash-loop | Migration failed — check deploy logs; restore snapshot (2b Option B) if schema bad |
| Duplicate scraping / racing writes | Two instances with `ENABLE_SCHEDULER=1` — set extras to `0` |
| Apple 403 storm | Circuit breaker will open; reduce job breadth; (proxies = post-launch fix) |
| Payments not activating | Check webhook delivery + signature secret; check Sentry; verify `PAYMENT_PROVIDER` |
| Charged-but-deleted user | Known gap until user-delete-cancels-subscription lands (Phase 2b) — cancel manually in gateway |
