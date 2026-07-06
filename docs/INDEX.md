# RankSpy — Master Technical Documentation (Project Bible)

> **Single source of truth for the RankSpy (`appstore-spy`) codebase.** Every statement is grounded in the actual code on the `audit-fixes` branch (12 commits ahead of `origin/main`). Nothing is invented.
>
> **Status legend:** ✅ Implemented · 🟡 Partially Implemented · 🔴 Planned / Not built.

---

## ⚡ Read this first

Three facts dominate everything in these documents:

1. **Nothing recent is live.** All 12 commits (security fixes, Alembic, scheduler hardening, the entire multi-country feature set) sit on a local branch — **unpushed, undeployed**. Production still runs old `main`.
2. **Data quality is unproven.** The estimates (the core value) are heuristic, uncalibrated, and contain a known math bug. There's no coverage/freshness instrumentation to even measure quality.
3. **The gap to a lovable product is *not* features** — it's shipping, measuring data quality, and calibrating the estimates.

If you read only two files, read **[01_EXECUTIVE_SUMMARY.md](./01_EXECUTIVE_SUMMARY.md)** and **[04_CTO_REVIEW.md](./04_CTO_REVIEW.md)**.

---

## 📚 Document map

| File | Covers | Requested sections |
|---|---|---|
| **[01_EXECUTIVE_SUMMARY.md](./01_EXECUTIVE_SUMMARY.md)** | Executive summary, product vision, **production-readiness scores (0–100)** | §1, §2, §23 |
| **[02_ARCHITECTURE.md](./02_ARCHITECTURE.md)** | Complete architecture, source-code structure, deployment/infra, monitoring/logging | §3, §4, §17, §18 |
| **[05_DATABASE.md](./05_DATABASE.md)** | All 43 tables, indexes, constraints, 5 Alembic migrations, schema drift, pool/conn analysis | §5 |
| **[06_API.md](./06_API.md)** | ~159 endpoints across 4 routers, auth model, country-awareness, API issues | §6 |
| **[07_FRONTEND.md](./07_FRONTEND.md)** | 33 routes, 21 components, api.ts client, UX/frontend issues | §7 |
| **[08_SCHEDULER_WORKERS.md](./08_SCHEDULER_WORKERS.md)** | 34 jobs, Discovery Engine, Queue system, data pipeline internals | §8, §9, §10 |
| **[10_DATA_PIPELINE.md](./10_DATA_PIPELINE.md)** | End-to-end pipeline, acquisition strategy, data quality & coverage, AI systems | §11, §12, §13, §19 |
| **[09_SECURITY_PERFORMANCE.md](./09_SECURITY_PERFORMANCE.md)** | Security review, performance review, scalability review | §14, §15, §16 |
| **[11_TECH_DEBT_DECISIONS.md](./11_TECH_DEBT_DECISIONS.md)** | Technical-debt register, decision log (ADRs), changelog | §20, §21, §22 |
| **[04_CTO_REVIEW.md](./04_CTO_REVIEW.md)** | 🔥 Brutally-honest CTO review — fix/add/remove/rewrite/redesign, every issue with impact + priority + effort + ROI | (review) |
| **[12_ROADMAP.md](./12_ROADMAP.md)** | Roadmap: Before-Production → MVP → V1 → V2 → Long-term | (roadmap) |
| **[13_NEXT_100_TASKS.md](./13_NEXT_100_TASKS.md)** | The Next 100 Engineering Tasks, priority-ordered with difficulty/deps/impact/prod-gate | (tasks) |

### Mapping of your 23 requested sections → files

| # | Requested section | File |
|---:|---|---|
| 1 | Executive Summary | 01 |
| 2 | Product Vision | 01 |
| 3 | Complete Architecture | 02 |
| 4 | Source Code Structure | 02 |
| 5 | Database Documentation | 05 |
| 6 | API Documentation | 06 |
| 7 | Frontend Documentation | 07 |
| 8 | Scheduler & Workers | 08 |
| 9 | Discovery Engine | 08 |
| 10 | Queue System | 08 |
| 11 | Data Pipeline | 10 |
| 12 | Data Acquisition Strategy | 10 |
| 13 | Data Quality & Coverage | 10 |
| 14 | Security Review | 09 |
| 15 | Performance Review | 09 |
| 16 | Scalability Review | 09 |
| 17 | Deployment & Infrastructure | 02 |
| 18 | Monitoring & Logging | 02 |
| 19 | AI Systems | 10 |
| 20 | Technical Debt | 11 |
| 21 | Decision Log | 11 |
| 22 | Changelog | 11 |
| 23 | Production Readiness Assessment | 01 |
| + | CTO Review · Roadmap · Next 100 Tasks | 04 · 12 · 13 |

---

## 🧭 Reading guides by role

- **Founder / PM:** 01 → 04 (CTO review) → 12 (roadmap). Ignore the deep reference files.
- **New engineer:** 02 (architecture) → 05 (db) → 06 (api) → 08 (workers) → 10 (pipeline).
- **Doing the next sprint:** 13 (next 100 tasks) — start at #1, go down. Tasks 1–20 are the whole game.
- **Security/ops:** 09 → 02 (monitoring) → 11 (debt).

---

## 📊 Project at a glance (from code)

| | |
|---|---|
| Stack | FastAPI + PostgreSQL (sync SQLAlchemy 2.0) · Next.js 14 · Railway |
| Scale | 43 tables · ~159 endpoints · 49 services · 34 jobs · 33 FE routes · 21 components |
| Migrations | 5 Alembic revisions (`0001`→`0005`) ✅ |
| Tests | 27 files (mostly unit; 1 country integration suite; 5 pre-existing failures) |
| AI | 2 services on Claude Haiku 4.5 (review summary + app autopsy); rest is rule-based |
| **Overall production readiness** | **~55 / 100** — foundation ~70, product-value (data) ~44, ops ~42 |
| **Deploy status** | 🔴 unpushed, undeployed — this is the #1 blocker |

*Generated as the definitive Project Bible. Regenerate the reference files (05–10) from code after major changes; keep 01/04/12/13 updated as strategy evolves.*
