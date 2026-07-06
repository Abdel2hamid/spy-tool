# 11 — Technical Debt, Decision Log & Changelog

> Part of the **RankSpy Project Bible**. See [INDEX.md](./INDEX.md). Legend: ✅ / 🟡 / 🔴.

---

## 20. Technical Debt Register

Ranked by risk × likelihood. Cross-referenced to the [CTO review](./04_CTO_REVIEW.md) issue numbers where applicable.

| ID | Debt | Location (code) | Risk | Sev |
|---|---|---|---|:--:|
| TD-1 | **Unbounded `rankings`/`reviews`** — no retention, partitioning, or unique constraint | models.py; no prune job | Storage cost + slow window queries as coverage grows | 🟥 |
| TD-2 | **Uncalibrated estimates + interpolation bug** | config/rank_curves.py, download/revenue_estimator | Wrong headline numbers → churn | 🟥 |
| TD-3 | **No cascade deletes** on 8 legacy `apps`/keyword child FKs; user-delete orphans workspace + live Stripe sub | models.py FKs; admin delete_user | Cannot delete; keeps billing deleted users | 🟧 |
| TD-4 | **Usage-counter race** (non-atomic increment on shared session) | plan_enforcement.py | Plan bypass; rollback of unrelated work | 🟧 |
| TD-5 | **Single egress IP** hardcoded; conservative caps everywhere pending proxies | apple_http_client, scheduler caps | Coverage ceiling | 🟧 |
| TD-6 | **In-memory cursors** for keyword daily jobs reset on redeploy | scheduler keyword jobs | Coverage skew after each deploy | 🟨 |
| TD-7 | **Duplicated logic**: 4–6 opportunity/difficulty/volume/CTR formulas; 3 app-upsert copies; 6 donut/score components (FE) | scoring/*, services, FE | Same metric, different numbers | 🟨 |
| TD-8 | **`current_rank` drift** — overwritten by last chart scraped, no chart context | scrape_top_charts | Wrong displayed rank | 🟨 |
| TD-9 | **Second uninsulated egress path** — `app_import_service` uses its own urllib (no breaker) | app_import_service.py | 403s bypass circuit breaker | 🟨 |
| TD-10 | **Legacy chart feed** `/us/rss` being sunset by Apple | scrapers/appstore.py | Future breakage | 🟨 |
| TD-11 | **Fragile HTML version-history scrape** | app_details.py | Breaks on Apple markup change | 🟨 |
| TD-12 | **Naive datetimes** at remaining sites | various | TZ drift in windows | 🟨 |
| TD-13 | **Oversized files**: routes.py 4.5K, engine.py 2.2K, apps/[id] 3.5K | — | Hard to change safely | 🟨 |
| TD-14 | **Dead code**: `weights.py`, v1 trending, `ideas/IdeasClient.tsx`, Playwright path, dup route names | — | Confusion/drift | 🟩 |
| TD-15 | **Unused deps**: python-multipart, numpy, scikit-learn, lxml, asyncpg | requirements*.txt | Build bloat | 🟩 |
| TD-16 | **JSON not JSONB**; can't GIN-index JSON columns | models.py | Query limits | 🟩 |
| TD-17 | **No frontend cache** (SWR/react-query); hand-fetch races | FE pages | UX/reliability | 🟨 |
| TD-18 | **`/health` "ok" overcount** — internally-caught job failures counted ok | scheduler `_with_timeout` | Misleading ops | 🟨 |
| TD-19 | **No CI/lint** (backend or frontend) | repo | Silent regressions | 🟧 |
| TD-20 | **Env drift** — dev runs Python 3.9, target 3.11 | local | "works on my machine" | 🟨 |

**Debt posture:** the recent audit paid down the *dangerous* debt (auth, migrations, thread-safety, crashers). What remains is mostly **scale/cost debt (TD-1, TD-5)** and **product-trust debt (TD-2)** — appropriate to tackle right after shipping.

---

## 21. Decision Log (ADR-style, reconstructed from code + git history)

| ADR | Decision | Rationale | Status | Trade-off |
|---|---|---|---|---|
| ADR-1 | **Monolith** (API + scheduler in one FastAPI process) | Simple + cheap on Railway; one deploy | ✅ Active | Can't scale API without `ENABLE_SCHEDULER=0`; shared resources |
| ADR-2 | **Postgres-only** (no Redis/Kafka/broker) | Fewer moving parts; queue = table + SKIP LOCKED | ✅ Active | Ceilings on queue throughput; in-proc caches only |
| ADR-3 | **Sync SQLAlchemy** (+asyncpg stripped) | Simpler mental model; most code is sync | ✅ Active | Async jobs must offload to threads to avoid blocking loop |
| ADR-4 | **Precompute-then-read** (trending/blowing-up/opportunities) | Cheap, uniform endpoint reads | ✅ Active | Staleness window; extra tables; per-country composite PKs |
| ADR-5 | **Adopt Alembic; remove startup DDL/DML** | Versioned, reviewable, non-destructive migrations | ✅ Active (this branch) | Baseline uses create_all + relocated historical DDL |
| ADR-6 | **Per-country via `rankings.country` + composite-PK score tables** | Isolate storefronts without new pipelines | ✅ Active (this branch) | Score tables grow ×countries; retention becomes urgent |
| ADR-7 | **SLA-weighted country rotation** for charts | Never-starve fairness on one IP | ✅ Active | Complexity; still IP-bound |
| ADR-8 | **Single egress IP, no proxies (yet)** | Cost; defer until needed | 🟡 Active | Hard coverage ceiling; conservative caps |
| ADR-9 | **Keywords stay US-only for now** | Scope; reviews/charts prioritized | 🟡 Active | "Global" incomplete for ASO persona |
| ADR-10 | **Heuristic estimates (no ground truth)** | No install-data source available | 🟡 Active | Accuracy risk; the core trust gap |
| ADR-11 | **JWT in localStorage** | Simple SPA auth | 🟡 Active | XSS token-theft surface |
| ADR-12 | **Rule-based intelligence** (opportunities/trending/ideas); LLM only for review-summary + autopsy | Cost control; determinism | ✅ Active | "AI" is mostly rules — clarify to buyers |

---

## 22. Changelog (this engagement — `audit-fixes` branch, 12 commits)

Chronological, newest last. All commits are **local/unpushed**.

| # | Commit | Summary |
|---|---|---|
| 1 | `c959257` | **Full-audit fixes** — security, correctness, reliability, performance (batch 1) |
| 2 | `d4ba5de` | **Audit fixes (batch 2)** — further security/reliability/perf |
| 3 | `614f6cd` | **Thread-safe scheduler sessions** — sessions created inside worker threads |
| 4 | `0c30b85` | **Remove blocking ORM from event loop** — offload heavy sync work to threads |
| 5 | `d894d65` | **Discovery cursor rotation** — persistent rotating chart cursor fixes combo starvation |
| 6 | `9bed207` | **Adopt Alembic** — versioned migrations; retire destructive startup DDL/DML |
| 7 | `8738cd4` | **Country dimension (db)** — `countries` table + `rankings.country` (rev 0002) |
| 8 | `fc4a9b4` | **Per-country Top Charts** — data + API + UI vertical |
| 9 | `94a3631` | **Widen to all countries** — SLA-weighted rotation (never-starve) |
| 10 | `41816db` | **Per-genre charts (per country)** — data + API + UI |
| 11 | `1a08b15` | **Country-aware Trending / Blowing-Up / Apps** — composite-PK score tables (rev 0005), tested |
| 12 | `2bec164` | **Per-country reviews** — multi-storefront collection + API + UI |

### Migrations added this engagement
`0001_baseline` → `0002_countries` → `0003_country_coverage` → `0004_ranking_genre` → `0005_score_country`. Verified fresh + existing-data + downgrade paths on Postgres 15.

### Tests added
`tests/test_country_aware.py` — 8 integration tests (trending/blowing-up per-country isolation, default/explicit/invalid country, empty datasets, reviews per storefront, review-countries). Gated on `TEST_DATABASE_URL`; all pass on Postgres 15.

### Net effect
US-only tool → **code-complete multi-storefront intelligence product** on a safer, versioned foundation. **Not yet pushed or deployed** — see [12_ROADMAP.md](./12_ROADMAP.md) Phase 0.
