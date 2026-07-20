# 08 — Scheduler & Background Workers

_Status: reflects the `audit-fixes` branch. Everything below is drawn directly from the source; file/line references are given so claims can be re-verified against code, not memory._

RankSpy runs **all** background processing in-process inside the FastAPI application via a single **APScheduler `AsyncIOScheduler`**. There is no external worker fleet, no Celery/RQ broker, and no cron. When the API process starts, the scheduler starts with it; when the process stops, the scheduler stops with it.

Primary sources:

| Concern | File |
| --- | --- |
| Scheduler + job definitions | `backend/app/workers/scheduler.py` |
| Scrape / scoring workers | `backend/app/workers/tasks.py` |
| Discovery engine + queue | `backend/app/workers/discovery_engine.py` |
| Keyword rank tracking job | `backend/app/jobs/keyword_rank_tracker.py` |
| Lifespan / scheduler gate | `backend/app/main.py` |
| Sync DB session factory | `backend/app/database/__init__.py` |

---

## 1. Scheduler Architecture

### 1.1 In-process AsyncIOScheduler (single instance)

The scheduler is a module-level singleton created once at import time (`scheduler.py:48`):

```python
scheduler = AsyncIOScheduler(timezone="UTC")
```

- **UTC everywhere.** The scheduler timezone is UTC, and every `IntervalTrigger` is constructed with `timezone="UTC"`. All `start_date` offsets are computed from `datetime.utcnow()` in `setup_scheduler()` (`scheduler.py:1735`).
- **Runs on the API event loop.** Because it's an `AsyncIOScheduler`, async jobs run as coroutines on the same event loop that serves HTTP. CPU-bound / blocking DB work is therefore explicitly off-loaded to threads (see §1.4) so it doesn't stall request handling.
- **Started from the lifespan context** in `main.py` (`main.py:59–90`), not at import.

### 1.2 Single-instance gate — `ENABLE_SCHEDULER`

The scheduler holds **in-process state** (rotating cursors, job metrics) and performs writes/queue claims. Running it in two replicas at once means duplicate scraping, duplicate writes, and racing queue claims. The gate (`main.py:75–82`) makes the scheduler opt-out:

```python
_scheduler_enabled = os.getenv("ENABLE_SCHEDULER", "1").lower() not in ("0", "false", "no")
if _scheduler_enabled:
    setup_scheduler()
    scheduler.start()
else:
    logger.info("Scheduler disabled via ENABLE_SCHEDULER — API-only instance")
```

**Operational contract:** exactly one replica may run with `ENABLE_SCHEDULER` unset/`1`; every additional (horizontally-scaled) replica must set `ENABLE_SCHEDULER=0` and serve API traffic only. This is a **convention enforced by deploy config, not by a distributed lock** — see Known Issues (§5.1).

Shutdown is non-blocking: `scheduler.shutdown(wait=False)` (`main.py:88`) — in-flight jobs are not awaited on shutdown.

### 1.3 Shared job defaults

Every recurring job is registered with `**_JOB_DEFAULTS` (`scheduler.py:53–58`):

| Default | Value | Effect |
| --- | --- | --- |
| `max_instances` | `1` | The same job never runs twice concurrently; a still-running job blocks its own next fire. |
| `coalesce` | `True` | Multiple missed fires collapse into one run (no backlog storms). |
| `misfire_grace_time` | `300` (5 min) | A fire more than 5 min late is skipped rather than run stale. |
| `replace_existing` | `True` | Re-registering on restart replaces the prior definition. |

> Note: the two non-decorated jobs (`bootstrap_data`, and the alerts job) are registered with an explicit `max_instances=1, replace_existing=True` but **not** the full defaults dict in the bootstrap case (`scheduler.py:1740–1747`).

### 1.4 `_with_timeout` wrapper + metrics (exposed via `/health`)

Nearly every job function is wrapped by `@_with_timeout(job_id)` (`scheduler.py:123–170`). The decorator:

1. Looks up a per-job timeout from `_JOB_TIMEOUTS` (`scheduler.py:64–97`), defaulting to `_DEFAULT_TIMEOUT = 1800`s.
2. Runs the coroutine under `asyncio.wait_for(fn(), timeout=...)`. On overrun it raises `asyncio.TimeoutError`, **cancels** the underlying task, and increments a `timeout` counter — a hung job can never block all future runs.
3. Maintains a per-job metrics dict in the module-level `_job_metrics` (`scheduler.py:103`): `runs`, `ok`, `fail`, `timeout`, `last_start`, `last_end`, `last_duration_s`.

`get_job_metrics()` (`scheduler.py:114`) returns a copy, surfaced in the `/health` payload under `job_metrics` (`main.py:369`). `/health` also reports scheduler running state, per-job `next_run` times, DB connectivity, **ranking freshness** (healthy `<6h`, stale `<24h`, critical `≥24h`), and **connection-pool status** (checked-in/out, overflow) — the key signals for diagnosing a stuck pipeline (`main.py:258–371`).

Two jobs are **not** decorated and therefore have **no timeout and no metrics**: `job_bootstrap_data` (one-shot) and `job_evaluate_alerts` (`scheduler.py:1497`, `1542`).

### 1.5 Thread-offload helper — `_run_in_thread_with_session`

The recent hardening centres on `_run_in_thread_with_session(fn, *args)` (`scheduler.py:201–235`). It runs `fn(session, ...)` in a worker thread (`asyncio.to_thread`) with a SQLAlchemy `Session` that the **thread itself creates, exclusively owns, and closes**:

```python
def _runner():
    db = SessionLocal()
    try:
        return fn(db, *args, **kwargs)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
return asyncio.to_thread(_runner)
```

Two invariants this guarantees:

- **A Session is never shared across threads.**
- **A coroutine timeout/cancellation can never close a Session mid-use.** Because the calling coroutine holds no reference to the session, an `asyncio.wait_for` timeout in `_with_timeout` cannot dispose a session the worker thread is still writing to.

Services commit their own work; the helper adds an explicit `rollback()` on exception before `close()`. This pattern is why blocking sync ORM and blocking `urllib` calls (e.g. `job_backfill_incomplete`, `scheduler.py:594–677`) were moved off the event loop.

> **Caveat / not fully consistent:** several jobs still open a raw `SessionLocal()` directly inside the coroutine and call `await engine.method(...)` where the engine method does its own `asyncio.to_thread` off-loading (the discovery jobs, keyword-pipeline jobs). Those are safe *because the engine off-loads internally*, but the session object itself is created on the loop thread. See §5.2.

---

## 2. Full Job Inventory

34 jobs are registered by `setup_scheduler()` (`scheduler.py:1730–2213`): **1 one-shot** (`bootstrap_data`) + **33 recurring**. "First run" is the `start_date` offset from process start; "Timeout" is the effective `_with_timeout` value (`—` = job is not timeout-wrapped). Trigger type is `IntervalTrigger` unless noted.

| # | Job ID | Interval | First run | Timeout | What it does |
| --- | --- | --- | --- | --- | --- |
| 1 | `bootstrap_data` | one-shot (`DateTrigger`) | +1 min | — (none) | If `rankings` is empty but apps have `current_rank`, seed initial ranking snapshots so trending/blowing-up can compute. Skips if rankings exist. |
| 2 | `ranking_refresh` | 2 h | +3 min | 600 s | Lightweight chart-RSS-only scrape of `topfree`+`topgrossing`, all-genres, **US**. Skips if newest ranking `<6h` old. Fixes ranking starvation on restart. |
| 3 | `country_charts` | 6 h | +8 min | 1800 s | SLA-weighted per-country top charts (free+grossing) for the most-overdue non-US storefronts; overall + tier-gated genres. (§3.3) |
| 4 | `discovery_keywords` | 6 h | +6 min | 3600 s | Run 100+ `DISCOVERY_KEYWORDS` via iTunes Search → enqueue new app IDs. |
| 5 | `discovery_charts` | 2 h | +10 min | 1800 s | Next batch of (chart × genre × country) combos via rotating cursor → enqueue app IDs (`batch_size=12`). (§3.2) |
| 6 | `discovery_developer` | 12 h | +14 min | 1800 s | For recently-added apps, fetch all other apps by that developer → enqueue (`limit=100`). |
| 7 | `queue_processor` | 30 min | +15 min | 3600 s | Claim up to 100 pending queue items, full-scrape (`concurrency=5`). Generic processor; excludes `tier_enrich:*` rows. |
| 8 | `hourly_reviews_ratings` | 1 h | +1 h | 3600 s | Quick refresh of rating/review-count/version + new reviews for **all** apps, priority-ordered, `max_wall_time=2700s`. |
| 9 | `hourly_scoring` | 1 h | +65 min | 3600 s | `run_scoring_task` in a thread: opportunity scores, market weakness, feature gaps, keyword scores, AI ideas, metric snapshots, daily report. |
| 10 | `full_metadata` | 6 h | +20 min | 7200 s | Full re-scrape of all tracked apps (metadata + versions + reviews) then chart rankings. |
| 11 | `backfill_incomplete` | 1 h | +3 min | 1800 s (default) | Bulk-backfill apps with `description IS NULL` via iTunes batch lookup (200 IDs/req, up to 1000 apps). Blocking `urllib` runs in a thread. |
| 12 | `keyword_rank_tracker` | 6 h | +30 min | 3600 s | Playwright App Store search scrape of tracked keywords (≤50/run), save snapshots, detect sponsored, update organic positions. (§ below) |
| 13 | `keyword_intelligence` | 12 h | +8 min | 7200 s | Full keyword pipeline: discover + Google Trends + Apple signals + optional DataForSEO + re-score (`max_keywords=5000`). |
| 14 | `keyword_scoring` | 6 h | +70 min | 3600 s | Recompute opportunity/feasibility scores from stored signals only (no external API). |
| 15 | `keyword_discovery` | 24 h | +20 min | 7200 s | Keyword expansion engine (alphabet/modifier + Apple autocomplete + n-gram) → `keywords` table. |
| 16 | `keyword_discovery_daily` | 24 h | +25 min | 7200 s | Per-app autocomplete/affix keyword discovery, 200 apps/run, **resumable via in-memory cursor**, wall-time budget 6000 s. |
| 17 | `keyword_discovery_phase1_daily` | 24 h | +30 min | 7200 s | Per-app alphabet + competitor + gap + opportunity scoring, 50 apps/run (4 calls/app), resumable in-memory cursor, budget 6000 s. |
| 18 | `opportunity_compute` | 1 h | +5 min | 600 s | Precompute "Opportunity of the Day" → `daily_opportunities` + legacy `DailyReport`. |
| 19 | `weekly_opportunities_compute` | 6 h | +7 min | 600 s | Precompute weekly Top-5 opportunities (ISO week); cache-through. |
| 20 | `blowing_up_compute` | 30 min | +4 min | 600 s | Momentum "blowing up" scores for apps with ≥2 snapshots in 7 d, all countries. |
| 21 | `trending_compute` | 30 min | +2 min | 300 s | Trending scores for all apps with recent ranking history, all storefronts. |
| 22 | `keyword_cleanup_daily` | 24 h | +45 min | 600 s | DELETE zero-volume stale `keywords` (>30 d) + low-score stale `app_discovered_keywords` (>30 d). |
| 23 | `keyword_quality_pruning` | 24 h | +2 h | 600 s | 6-rule quality prune of the global `keywords` table incl. Tier-C cap to <850k (`prune_keywords_job`). |
| 24 | `review_scraper` | 6 h | +90 min | 3600 s | Deep review ingestion: US top 300 apps + up to 4 Tier-1 non-US storefronts (40 apps each). Multi-country. (§ below) |
| 25 | `sentiment_analysis` | 1 h | +35 min | 600 s | Rule-based classify of `sentiment IS NULL` reviews + roll-up into `app_analytics`. |
| 26 | `feature_gap` | 2 h | +50 min | 1800 s | FeatureGapAnalyzer for apps with ≥5 reviews → `feature_gaps`. |
| 27 | `ad_intelligence` | 6 h | +70 min | 3600 s | Growth phase 3: ad detection (Apple Search Ads heuristic + Meta Ads if token) for momentum-flagged candidates. |
| 28 | `campaign_detection` | 2 h | +80 min | 1800 s | Growth phase 4: classify growth patterns from existing tables (read-only, no scraping). |
| 29 | `mass_discovery_light` | 6 h | +20 min | 3600 s | 1000+ long-tail `MASS_KEYWORDS` → pre-filter (score ≥15) → light insert (`ingestion_stage='light'`). |
| 30 | `tier_reclassify` | 6 h | +25 min | 600 s | Single SQL `CASE WHEN` UPDATE reclassifying apps into HOT/WARM/COLD (skips rows updated <6 h ago). |
| 31 | `enrich_hot` | 1 h | +30 min | 1800 s | Enqueue HOT light apps (≤200) then process queue `tier="hot"`, `concurrency=5`. |
| 32 | `enrich_warm` | 6 h | +90 min | 3600 s | Enqueue WARM light apps (≤500) then process queue `tier="warm"`, `concurrency=5`. |
| 33 | `enrich_cold` | 24 h | +4 h | 3600 s | Enqueue COLD light apps (≤1000) then process queue `tier="cold"`, `concurrency=3`. |
| 34 | `evaluate_alerts` | 1 h | +40 min | — (none) | Evaluate active user alert rules (trending / keyword-rising / new-opportunity / rank-drop) → `AlertEvent`; 6 h dedup window. |

**Notes on timeouts:** `_JOB_TIMEOUTS` (`scheduler.py:64–97`) also lists ids that are not currently registered as recurring jobs (e.g. `analytics_update` removed; some listed keys map 1:1). `backfill_incomplete` is absent from `_JOB_TIMEOUTS`, so it takes `_DEFAULT_TIMEOUT` (1800 s).

---

## 3. Discovery Engine

`DiscoveryEngine` (`discovery_engine.py:199`) finds App Store app IDs from four complementary sources and feeds them into the `discovery_queue` for background full scraping. Progress is tracked in `discovery_progress` so each source is re-fetched at most once/day and survives restarts.

### 3.1 The four discovery sources

| Source | Method | Fetch | Config |
| --- | --- | --- | --- |
| **Charts** | `run_chart_discovery_batch` | iTunes RSS chart feeds | 3 chart slugs × 21 genres (+all) × 20 countries (`discovery_engine.py:40–76`) |
| **Keywords** | `run_keyword_discovery` / `run_mass_keyword_discovery` | iTunes Search API | 100+ `DISCOVERY_KEYWORDS`; 1000+ derived `MASS_KEYWORDS` |
| **Developer** | `run_developer_expansion` | iTunes artist lookup | all apps by each already-known developer |
| **Related** | (via iTunes artist/software lookup) | iTunes lookup | surfaced through developer/lookup calls |

All HTTP fetch helpers are `@staticmethod` and are always invoked through `asyncio.to_thread` so blocking HTTP never touches the event loop (`discovery_engine.py:319–489`, `680–824`).

**Priority signal:** keyword discovery assigns queue priority from release-date freshness — `5` (<30 d) / `4` (<90 d) / `2` (older/unknown) via `_freshness_priority` (`discovery_engine.py:447–469`) — so fresh apps jump the queue.

### 3.2 Rotating chart cursor — fixes starvation ✅

The chart combo space is `3 × 21(+1) × 20 = 1,320` combos. Previously each daily run restarted at combo 0, so later combos were never reached. The fix is a **persistent rotating cursor** stored in `discovery_progress` under `source_key = "chart:_cursor"` (the `apps_found` column doubles as the flattened index) (`discovery_engine.py:295–313`):

- `run_chart_discovery_batch` flattens combos in a fixed order, starts at `cursor % n`, and processes up to `batch_size` combos that haven't run today (`discovery_engine.py:680–726`).
- After the run it advances the cursor **past everything scanned** (including already-ran-today combos), so the next run continues where this one stopped and wraps around — every combo is eventually reached. Being in the DB, it survives restarts.

### 3.3 `country_charts` SLA rotation — never-starve ✅

Distinct from chart *discovery*, `job_country_charts` (`scheduler.py:472–541`) writes **per-country ranking rows** for every enabled storefront using SLA-weighted rotation:

- A country is **due** once `now() - charts_last_covered_at > sla_hours` (or never covered). US is excluded (owned by `ranking_refresh`).
- Due countries are ordered by **staleness ratio** = `hours_since_covered / sla_hours` **DESC**, limited to `_COUNTRY_CHART_BATCH = 25` per run (`scheduler.py:462`). Short-SLA (high-tier) countries refresh often; a never-covered / long-overdue country has an ever-growing ratio and is *always eventually picked* — **no country starves**.
- Each due country fetches **overall + tier-gated genres** via `_GENRES_FOR_TIER` (`scheduler.py:466–469`): Tier 1 → 6 genres, Tier 2 → 3 genres, Tier 3/4 → overall only.
- `charts_last_covered_at` is stamped **per-country immediately after each is scraped** (`_mark_covered`, `scheduler.py:514–519`), so a mid-run timeout is resumable — completed countries aren't redone. 0.5 s pacing between storefronts.

### 3.4 Tier enrichment (HOT / WARM / COLD)

A two-speed pipeline: discovery does cheap "light" inserts (`ingestion_stage='light'`, `light_insert_batch`, `discovery_engine.py:495–563`); `tier_reclassify` labels each app's `sync_tier`; then the three enrich jobs promote light apps to full metadata by tier:

| Tier | Job / cadence | Enqueue cap | Queue priority | `process_queue` concurrency |
| --- | --- | --- | --- | --- |
| HOT | `enrich_hot` / 1 h | 200 | 5 | 5 |
| WARM | `enrich_warm` / 6 h | 500 | 2 | 5 |
| COLD | `enrich_cold` / 24 h | 1000 | 0 | 3 |

Each enrich job runs in two phases (`scheduler.py:835–909`): **(1)** `_enqueue_light_apps_for_tier` (quick DB op via `_run_in_thread_with_session`) selects light apps of that tier **not already queued** (a `NOT EXISTS` subquery, not an in-memory ID load — `discovery_engine.py:605–657`) and inserts `tier_enrich:{tier}` queue rows; **(2)** a fresh `SessionLocal()` drives `process_queue(tier=...)`, which filters to `source LIKE '%tier_enrich:{tier}%'` so tiers don't steal each other's work.

---

## 4. Queue System (`discovery_queue`)

The queue is a plain Postgres table, not a broker. Producers = discovery jobs; consumers = `queue_processor` and the three enrich jobs.

### 4.1 Enqueue + dedup — `ON CONFLICT DO NOTHING`

`enqueue()` (`discovery_engine.py:218–263`):

1. Dedups against the **apps table** first (skip IDs that already exist as apps).
2. Bulk-inserts remaining IDs with `pg_insert(...).on_conflict_do_nothing(index_elements=["app_id"])`. `app_id` is unique on the queue, so a concurrent discovery job racing the same ID can't poison the whole batch with an `IntegrityError` — the conflict is silently dropped. Returns `rowcount` newly added.

Rows carry `source`, `priority`, `status='pending'`, and `enrich_mode` (`'full'` | `'light'`) so the processor knows which scrape path to use.

### 4.2 Claiming — `FOR UPDATE SKIP LOCKED`

`process_queue()` (`discovery_engine.py:830–965`):

1. Selects up to `batch_size` `pending` rows ordered by `priority DESC, added_at DESC` with `.with_for_update(skip_locked=True)` — concurrent claimers skip locked rows, so two consumers never grab the same item.
2. Atomically marks the claimed IDs `status='scraping'` and stamps `processed_at` (the claim timestamp) in one UPDATE + commit.
3. Scrapes with a semaphore capped at `min(concurrency, 5)` (`discovery_engine.py:915`) — each worker uses its own `ScraperWorker` session and updates the queue row in a **separate** `SessionLocal()` (`db2`) to avoid cross-session interference.
4. Per-item outcome: success → `status='done'`; failure → `failed_attempts += 1`, back to `pending` until it reaches 3 attempts, then `status='failed'` (`discovery_engine.py:944–951`).

The generic `queue_processor` explicitly **excludes** `tier_enrich:*` rows (NULL-safe filter, `discovery_engine.py:876–884`) so it doesn't double-scrape rows owned by the enrich jobs.

### 4.3 Stale-claim reaper

At the **start** of every `process_queue` call, rows stuck in `scraping` are reclaimed (`discovery_engine.py:858–869`): any `scraping` row whose `processed_at` is NULL (claimed before claim-stamping existed) or older than `now() - 2h` is reset to `pending`. This recovers items orphaned by a job timeout or a mid-batch container restart — otherwise they'd be lost forever.

### 4.4 Retention

**There is no queue retention / cleanup.** 🟡 `done` and `failed` rows are never purged — the table grows monotonically. `get_metrics()` (`discovery_engine.py:971–1058`) counts `pending`/`scraping`/`done`/`failed` for observability but nothing deletes them. Likewise there is **no retention on `rankings`, `keyword_search_snapshots`, or `reviews`** — only `keywords` / `app_discovered_keywords` are pruned (jobs 22–23). See §5.3.

---

## 5. Known Issues (from code)

Severity: 🔴 high · 🟡 medium · ✅ mitigated / by-design

### 5.1 Single-instance assumption — 🟡 (mitigated by convention)
The scheduler keeps **in-process** state (rotating cursors, `_job_metrics`, resumable cursors) and races queue claims. Two replicas both running it → duplicate scraping, duplicate writes, racing claims. Mitigated by the `ENABLE_SCHEDULER` gate (`main.py:75–82`), but this is a **deploy-config convention, not a distributed lock / leader election** — a misconfigured second scheduler replica silently duplicates work. The queue's `SKIP LOCKED` + `ON CONFLICT` limits the damage on the queue path, but chart cursors, ranking writes, and score recomputes are not similarly protected.

### 5.2 Remaining sync ORM on the event loop — 🟡
The hardening moved heavy jobs to `_run_in_thread_with_session`, but several jobs still construct a `SessionLocal()` **directly in the coroutine** and issue ORM queries there before/around the off-loaded HTTP work: `discovery_keywords`, `discovery_charts`, `discovery_developer`, `queue_processor`, `keyword_intelligence`, `keyword_scoring`, `keyword_discovery`, `mass_discovery_light`, and the cursor-load blocks of `keyword_discovery_daily` / `phase1_daily` (`scheduler.py:684–1239`). These are *mostly* safe because the engines off-load HTTP internally via `asyncio.to_thread`, but the initial ORM `.all()` / `.count()` queries and the `process_queue` claim SELECT/UPDATE execute on the loop thread and can still block it under a slow DB.

### 5.3 No queue / rankings / snapshot retention — 🟡
`discovery_queue` (`done`/`failed`), `rankings`, `keyword_search_snapshots`, and `reviews` have **no pruning job**. On a long-running deployment these tables grow without bound, degrading query performance and inflating storage. Only the `keywords` family is pruned (jobs 22–23).

### 5.4 In-memory cursors reset on redeploy — 🟡
`_kw_discovery_daily_cursor` and `_kw_discovery_phase1_cursor` are **module globals** (`scheduler.py:110–111`), not persisted. Every container restart resets them to 0, so per-app keyword discovery restarts from the lowest `App.id` and repeatedly re-covers the same early apps while high-id apps may be starved if restarts are frequent. Contrast with the chart cursor, which was deliberately moved to the DB (§3.2). The daily job comments acknowledge this is "fine" because it cycles over multiple runs — true only between restarts.

### 5.5 Duplicated computation across jobs — 🟡
Several scoring paths overlap:
- `hourly_scoring` → `ScoringWorker.update_opportunities()` (`tasks.py:612–790`) recomputes **feature gaps** (`FeatureGapAnalyzer`), **keyword intelligence scores**, and **market weakness** — while the dedicated jobs `feature_gap` (job 26) and `keyword_scoring` (job 14) recompute the same things on their own cadence.
- `hourly_scoring` also does keyword pruning (`update_opportunities` marks + deletes `pruned` keywords) that overlaps with `keyword_cleanup_daily` (22) and `keyword_quality_pruning` (23).
- `discovery_keywords` (100+ keywords, 6 h) and `mass_discovery_light` (same base list + modifiers, 6 h) re-run overlapping keyword sets; the code comment at `scheduler.py:2130–2132` notes the redundancy and that results are deduplicated downstream, so the cost is wasted API calls rather than duplicate rows.

The redundancy is bounded by dedup/`ON CONFLICT`/`_ran_today` gating (so it rarely corrupts data), but it wastes DB connections, CPU, and external API budget.

### 5.6 Pool pressure from many concurrent jobs — 🟡
33 recurring jobs share one engine pool sized `pool_size=20, max_overflow=30` (total 50) with a 60 s `statement_timeout` (`database/__init__.py:9–18`). Concurrency inside jobs is deliberately capped (`process_queue` → `min(concurrency,5)`; `scrape_quick_refresh_all` → semaphore 5; enrich jobs open a second session) precisely to avoid pool exhaustion, and `/health` surfaces live pool counts (`main.py:347–360`) — but overlapping heavy jobs (e.g. `full_metadata` + `queue_processor` + `enrich_*`) can still contend for connections. Managed, not eliminated.

---

## Appendix — the `keyword_rank_tracker` and multi-country `review_scraper` specifics

**`keyword_rank_tracker`** (`jobs/keyword_rank_tracker.py`): selects ≤50 keywords ordered by `quality_tier` (A/B/C) then `quality_score`/`apps_count`/`times_seen`/`search_volume`, filtering to 3–40-char alphabetic terms. Scrapes real App Store search results via Playwright (`AppStoreSearchScraper`, `concurrency=2` tabs, ≤20 results/keyword), saves rows to `keyword_search_snapshots` tagged sponsored vs organic, and updates `AppKeyword.position` from organic ranks. Runs on a single `SessionLocal()` closed in `finally`.

**`review_scraper`** multi-country (`scheduler.py:1318–1361`): US gets deep coverage (`_REVIEW_APP_LIMIT = 300`); then up to `_REVIEW_INTL_COUNTRIES_MAX = 4` enabled Tier-≤1 non-US storefronts get bounded coverage (`_REVIEW_INTL_APP_LIMIT = 40` apps each). New reviews are persisted tagged with their `storefront`; existing reviews (by `review_id`) are skipped. Conservative caps are intentional because review scraping is request-heavy on a single egress IP (`scheduler.py:1311–1315`).
