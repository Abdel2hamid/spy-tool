# 13 — The Next 100 Engineering Tasks

> Part of the **RankSpy Project Bible**. See [INDEX.md](./INDEX.md).
> Ordered **highest → lowest priority by ROI / business impact**. Columns: **Diff** (S<1d · M 1–3d · L 1–2w · XL 3w+) · **Deps** (task #s) · **Impact** · **Prod?** (🚦 = required before production · ⏳ = can wait).

Grounded in the actual code + the [CTO review](./04_CTO_REVIEW.md). The first ~15 are the ones that actually move the business; do them in order.

## Tier A — Ship & de-risk (do first)

| # | Task | Diff | Deps | Impact | Prod? |
|---:|---|:--:|:--:|---|:--:|
| 1 | Push `audit-fixes` + open PR | S | — | Unblocks everything; backs up 12 commits | 🚦 |
| 2 | CI: run pytest + `tsc` + `next build` on push (pin Python 3.11) | M | 1 | Catch regressions | 🚦 |
| 3 | Fix/quarantine 5 broken `test_reviews_intelligence` mocks | S | 2 | Green CI baseline | 🚦 |
| 4 | Add Postgres service to CI; run `test_country_aware` integration suite | S | 2 | Verify country isolation in CI | 🚦 |
| 5 | Railway **staging** environment | M | 1 | Test migrations/pipeline safely | 🚦 |
| 6 | Deploy branch to staging; smoke-test all core flows | M | 5 | Confidence before prod | 🚦 |
| 7 | Deploy to prod; watch Alembic `0001→0005` boot | S | 6 | Cutover; closes live security holes | 🚦 |
| 8 | Sentry (backend + frontend) | S | — | Know when it breaks | 🚦 |
| 9 | Alerts: job-failure / 403-storm / migration-failure | M | 8 | Ops visibility | 🚦 |
| 10 | Coverage/freshness metrics endpoint + table (apps by country/source, freshness, rows/day) | M | 7 | **See data quality** | 🚦 |

## Tier B — Data trust & money integrity

| # | Task | Diff | Deps | Impact | Prod? |
|---:|---|:--:|:--:|---|:--:|
| 11 | Fix `rank_curves.interpolate_rank_downloads` (monotonic + continuous) | M | — | Stop wrong estimates | 🚦 |
| 12 | Atomic usage-counter (`UPDATE … RETURNING`), dedicated session | S | — | Stop revenue leak | 🚦 |
| 13 | Stripe idempotency keys on customer/checkout create | S | — | Prevent dup customers | 🚦 |
| 14 | Rankings **change-only writes** + daily heartbeat per tier | M | — | Cut row volume 10×+ | 🚦 |
| 15 | Month-partition `rankings`; retention + rollup (T1 90d→weekly) | L | 14 | Storage/cost control | 🚦 |
| 16 | Reviews retention/cap; `discovery_queue` done-row pruning | M | — | Storage control | ⏳ |
| 17 | Cascade deletes on 8 legacy `apps`/`keywords` child FKs (+ passive_deletes) | M | — | Enable deletion; GDPR | 🚦 |
| 18 | User-delete cancels Stripe subscription + deletes sole-owner workspace | M | 17 | Stop billing deleted users | 🚦 |
| 19 | Unique constraint on `app_analytics.app_id` + ON CONFLICT upsert | S | — | Stop analytics fork | ⏳ |
| 20 | Weekly accuracy spot-check (20 apps vs live App Store) + fix parsing | M | 10 | Prove/repair correctness | 🚦 |

## Tier C — Coverage & acquisition scale

| # | Task | Diff | Deps | Impact | Prod? |
|---:|---|:--:|:--:|---|:--:|
| 21 | Proxy pool + keep-alive HTTP client + per-IP circuit breaker | M | — | Break single-IP ceiling | ⏳ |
| 22 | Route `app_import_service` through the hardened Apple client | S | — | Remove 2nd uninsulated egress path | ⏳ |
| 23 | Widen `country_charts` rotation T1→T3 (after 15,21) | S | 15,21 | Real global charts | ⏳ |
| 24 | Persist keyword-daily cursors in DB (stop redeploy reset) | S | — | Fix coverage skew | ⏳ |
| 25 | Batched `/lookup` (200 ids) metadata refresh + signal-hash change detection | M | — | Cheap freshness at scale | ⏳ |
| 26 | Migrate legacy `/us/rss` charts to `rss.marketingtools.apple.com` | S | — | Feed being sunset by Apple | ⏳ |
| 27 | App-ID enumeration / sitemap ingestion (catalog tail) | M | 21 | Coverage step-change | ⏳ |
| 28 | Estimate ground-truth calibration (rank→downloads per country×category) | L | 11,10 | Best-in-class accuracy | ⏳ |
| 29 | Confidence bands in estimate UI (honest uncertainty) | S | 28 | Trust | ⏳ |
| 30 | Fix `current_rank` drift (store rank + chart context, or derive at read) | M | — | Correct headline rank | ⏳ |

## Tier D — Correctness & reliability cleanup

| # | Task | Diff | Deps | Impact | Prod? |
|---:|---|:--:|:--:|---|:--:|
| 31 | Move remaining sync ORM off event loop (evaluate_alerts done; audit rest) | M | — | No loop stalls | ⏳ |
| 32 | Fix `/health` job "ok" overcount (re-raise or count in `_log_fail`) | S | — | Honest ops metrics | ⏳ |
| 33 | Replace remaining naive `datetime.utcnow()` with tz-aware | S | — | TZ correctness | ⏳ |
| 34 | Stale-`scraping` reaper already exists — add claimed_at column for precision | S | — | Queue hygiene | ⏳ |
| 35 | `to_thread` timeout jobs: cooperative deadlines (session refactor mostly done) | M | — | Avoid overlap on timeout | ⏳ |
| 36 | Typed Apple-client errors (blocked/rate-limited/empty) vs None | M | — | Stop committing partial data as success | ⏳ |
| 37 | Incremental reviews (stop at last-seen review_id) | S | — | ~10× fewer review requests | ⏳ |
| 38 | Fix review pagination edge cases / dev-reply fields (AMP API) | M | — | Review depth/quality | ⏳ |
| 39 | Version-history scrape via AMP API (fragile HTML scrape broken) | M | — | Metadata completeness | ⏳ |
| 40 | Keyword-gap top-50 already fixed; audit other 20-vs-30 mismatches | S | — | Fewer false gaps | ⏳ |

## Tier E — Performance

| # | Task | Diff | Deps | Impact | Prod? |
|---:|---|:--:|:--:|---|:--:|
| 41 | pg_trgm GIN index on `primary_category`/`secondary_category` (ILIKE) | S | — | Kill category seq scans | ⏳ |
| 42 | Batch N+1 in admin `list_users`/`list_workspaces`/CSV export | M | — | Faster admin | ⏳ |
| 43 | Batch ASO score in `list_my_apps` loop | S | — | Faster my-apps | ⏳ |
| 44 | Add indexes implied by hot WHERE/ORDER BY (subscriptions.stripe_customer_id, partial `sentiment IS NULL`) | S | — | Faster webhooks/sentiment job | ⏳ |
| 45 | Convert `async def` routes doing sync ORM to `def` (or offload) | M | — | Free the loop | ⏳ |
| 46 | Per-item worker/session reuse in `process_queue` | M | — | Less churn | ⏳ |
| 47 | Keyset-paginate remaining `iter_batches` OFFSET callers | S | — | O(n) not O(n²) | ⏳ |
| 48 | Pool sizing review (pool_size vs Railway cap; separate job pool/NullPool) | S | — | Avoid conn exhaustion | ⏳ |
| 49 | Cache `/categories` + reference data (in-proc TTL) | S | — | Fewer repeated queries | ⏳ |
| 50 | Downsample old rankings (rollup job) | M | 15 | Query speed | ⏳ |

## Tier F — Frontend & UX

| # | Task | Diff | Deps | Impact | Prod? |
|---:|---|:--:|:--:|---|:--:|
| 51 | Adopt SWR/react-query (cache, dedup, retry, kill races) | M | — | UX + reliability in one move | ⏳ |
| 52 | Error states everywhere (stop rendering failures as empty) | M | 51 | Trust/activation | ⏳ |
| 53 | Onboarding / first-run empty-state guidance | M | — | Activation | ⏳ |
| 54 | Split `apps/[id]/page.tsx` (3.5K) into tabs + lazy-load | M | — | Bundle/maintainability | ⏳ |
| 55 | Country selector on apps-list (per-country rank view) + opportunities | M | — | Consistency of "global" | ⏳ |
| 56 | Extract shared `ScoreRing`/`ScoreBar`/`fmtNum` (6× dup) | S | — | Consistency | ⏳ |
| 57 | `next/image` for icons/screenshots | S | — | Perf | ⏳ |
| 58 | Delete dead `ideas/IdeasClient.tsx`; fix Dashboard link | S | — | Dead code | ⏳ |
| 59 | Consistent number/date formatting (one helper) | S | — | Polish | ⏳ |
| 60 | ESLint config + fix warnings | S | — | Quality gate | ⏳ |
| 61 | Rating distribution: use server aggregate not 20-sample | M | — | Correct sentiment | ⏳ |
| 62 | AbortController on all `[id]`-keyed effects (some done) | M | 51 | No stale overwrites | ⏳ |
| 63 | Fix per-keystroke import already fixed — audit other debounce bugs | S | — | UX | ⏳ |
| 64 | Impersonation token restore UX (backup added; add "stop impersonating") | S | — | Admin UX | ⏳ |
| 65 | Mobile/responsive pass on data tables | M | — | Usability | ⏳ |

## Tier G — Data model & consolidation

| # | Task | Diff | Deps | Impact | Prod? |
|---:|---|:--:|:--:|---|:--:|
| 66 | Consolidate 4–6 `opportunity_score`/difficulty/volume/CTR formulas | M | — | One metric, one number | ⏳ |
| 67 | Single shared `upsert_app_from_itunes` (replace 3 copies) | M | — | Consistent records | ⏳ |
| 68 | JSON → JSONB (+ GIN where queried) | M | — | Query capability | ⏳ |
| 69 | Remove dead scoring code (`weights.py`, v1 trending, unused fns) | S | — | Clarity | ⏳ |
| 70 | Remove unused deps (multipart/numpy/sklearn/lxml/asyncpg) | S | — | Slimmer builds | ⏳ |
| 71 | Fix duplicate route-function names in routes.py | S | — | Avoid shadowing | ⏳ |
| 72 | Split `routes.py` (4.5K) into domain routers | M | — | Maintainability | ⏳ |
| 73 | Keyword pruning consolidation (3 places → 1 owner) | M | — | Less churn/conflict | ⏳ |
| 74 | Standardize tz-aware datetimes repo-wide (lint rule) | S | 33 | Correctness | ⏳ |
| 75 | Alembic autogenerate proper baseline once DB is canonical | M | 7 | Cleaner migrations | ⏳ |

## Tier H — Keywords-per-country (the deferred global half)

| # | Task | Diff | Deps | Impact | Prod? |
|---:|---|:--:|:--:|---|:--:|
| 76 | Localized keyword seed sets per storefront language | M | — | ASO global | ⏳ |
| 77 | Per-country keyword-rank snapshots (schema + collect) | L | 76,21 | Core ASO data | ⏳ |
| 78 | Autocomplete-driven keyword expansion per locale | M | 76 | Long-tail keywords | ⏳ |
| 79 | Country param through keyword endpoints + UI selector | M | 77 | Consistent global | ⏳ |
| 80 | Per-country keyword difficulty/volume | L | 77 | ASO depth | ⏳ |

## Tier I — Scale (Discovery Engine V2)

| # | Task | Diff | Deps | Impact | Prod? |
|---:|---|:--:|:--:|---|:--:|
| 81 | Extract scheduler drainers into a dedicated worker service | L | 7 | Horizontal scale | ⏳ |
| 82 | Tiered request-budget lanes (discovery vs refresh floors) | L | 81 | Fair acquisition | ⏳ |
| 83 | AIMD adaptive rate governor (per-IP) | M | 21 | Use IPs safely | ⏳ |
| 84 | Regional worker shards | L | 81 | Throughput | ⏳ |
| 85 | PgBouncer / connection pooling | S | — | Conn scale | ⏳ |
| 86 | Read replica for API reads | M | — | Read scale | ⏳ |
| 87 | Per-country sentiment rollups (app_analytics country dim) | M | — | Review intelligence | ⏳ |
| 88 | AMP catalog/reviews API integration | M | — | Metadata/review quality | ⏳ |

## Tier J — Product & growth

| # | Task | Diff | Deps | Impact | Prod? |
|---:|---|:--:|:--:|---|:--:|
| 89 | CSV/API exports | M | — | Stickiness | ⏳ |
| 90 | Watchlists/alerts polish (model exists) | M | — | Retention | ⏳ |
| 91 | Team seats / roles (workspace model exists) | M | — | ACV expansion | ⏳ |
| 92 | Public data API product | L | 81 | New revenue | ⏳ |
| 93 | Cache app-autopsy LLM narrative (currently uncached, cost) | S | — | AI cost | ⏳ |
| 94 | Centralize AI model id + typed error handling | S | — | AI reliability | ⏳ |
| 95 | Email-verify token single-use (jti flip) + POST | S | — | Auth hardening | ⏳ |
| 96 | httpOnly cookie auth (move token off localStorage) | M | — | XSS blast radius | ⏳ |
| 97 | Rate-limit key hardening (trusted-proxy config) | S | — | Abuse control | ⏳ |
| 98 | Backup/restore runbook (verify Railway PG backups) | S | — | DR | 🚦 |
| 99 | Encrypt payment secrets at rest (not plaintext admin_settings) | S | — | Security | ⏳ |
| 100 | Android / Google Play exploration spike | L | — | TAM ×2 (long-term) | ⏳ |

---

### How to read this list
- **The first 20 are the whole game.** If you only do Tier A + B, you have a live, safe, trustworthy product — which beats a broader-but-unshipped one.
- **🚦 = required before production** (13 tasks). Everything else can follow.
- Dependencies are minimal by design — the list is front-loaded so you can start at #1 and go straight down.
