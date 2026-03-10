"""
Backfill Keyword Structure
==========================
One-time migration that promotes existing ``app_discovered_keywords`` data into
the normalised 3-table architecture:

  keywords        (dictionary)
  keyword_metrics (intelligence signals)
  app_keywords    (app→keyword relations)

Steps
-----
1. Read all distinct (app_id, keyword, metrics) rows from ``app_discovered_keywords``.
2. Upsert each unique keyword term into ``keywords`` (ON CONFLICT DO NOTHING).
3. Resolve ``keyword_id`` for every term.
4. Upsert rows into ``app_keywords`` (app_id, keyword_id, rank, traffic,
   opportunity_score, source) — ON CONFLICT DO NOTHING.
5. Upsert rows into ``keyword_metrics`` (keyword_id, search_volume, difficulty,
   trend_score) — ON CONFLICT DO UPDATE SET … (keeps freshest metrics).

Usage
-----
Run once after deploying the new schema migration::

    from app.database import SessionLocal
    from app.services.backfill_keyword_structure import backfill_keyword_structure

    db = SessionLocal()
    try:
        stats = backfill_keyword_structure(db)
        print(stats)
    finally:
        db.close()

Or trigger via the API endpoint (if wired up) or a one-off script.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500
_MAX_PER_APP = 100
_MAX_GLOBAL = 1_000_000


def backfill_keyword_structure(db: Session) -> Dict[str, int]:
    """
    Migrate ``app_discovered_keywords`` → ``keywords`` + ``keyword_metrics``
    + ``app_keywords``.

    Returns a stats dict with keys:
      terms_inserted, terms_skipped, app_keywords_inserted, metrics_upserted,
      apps_processed, rows_read
    """
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.models import Keyword, KeywordMetrics, AppKeyword

    now = datetime.now(timezone.utc)
    stats = {
        "terms_inserted": 0,
        "terms_skipped": 0,
        "app_keywords_inserted": 0,
        "metrics_upserted": 0,
        "apps_processed": 0,
        "rows_read": 0,
    }

    # ── Step 1: load all rows from app_discovered_keywords ────────────────────
    rows = db.execute(
        text(
            "SELECT app_id, keyword, search_volume, difficulty, traffic_score, "
            "app_rank, opportunity_score, source "
            "FROM app_discovered_keywords "
            "ORDER BY app_id, opportunity_score DESC"
        )
    ).fetchall()

    stats["rows_read"] = len(rows)
    if not rows:
        logger.info("[Backfill] app_discovered_keywords is empty — nothing to migrate")
        return stats

    logger.info(f"[Backfill] Starting migration of {len(rows)} app_discovered_keywords rows")

    # ── Step 2: collect unique terms, check global limit ─────────────────────
    all_terms = list({r.keyword for r in rows})
    global_count = db.query(Keyword.id).count()
    if global_count >= _MAX_GLOBAL:
        logger.warning(
            f"[Backfill] global keyword limit reached ({global_count:,}) — skipping"
        )
        return stats

    terms_to_insert = all_terms[: _MAX_GLOBAL - global_count]

    # ── Step 3: upsert unique terms into keywords ─────────────────────────────
    for i in range(0, len(terms_to_insert), _BATCH_SIZE):
        batch = terms_to_insert[i : i + _BATCH_SIZE]
        try:
            stmt = (
                pg_insert(Keyword.__table__)
                .values(
                    [
                        {
                            "term": t,
                            "keyword_source": "backfill",
                            "first_seen_at": now,
                        }
                        for t in batch
                    ]
                )
                .on_conflict_do_nothing(index_elements=["term"])
            )
            result = db.execute(stmt)
            db.commit()
            batch_inserted = result.rowcount or 0
            stats["terms_inserted"] += batch_inserted
            stats["terms_skipped"] += len(batch) - batch_inserted
        except Exception as exc:
            db.rollback()
            logger.error(f"[Backfill] keyword batch insert failed: {exc}", exc_info=True)

    logger.info(
        f"[Backfill] keywords: {stats['terms_inserted']} inserted, "
        f"{stats['terms_skipped']} already existed"
    )

    # ── Step 4: build term → keyword_id mapping ───────────────────────────────
    id_map: Dict[str, int] = {
        row.term: row.id
        for row in db.query(Keyword.id, Keyword.term)
        .filter(Keyword.term.in_(all_terms))
        .all()
    }

    # ── Step 5: group rows by app_id, enforce per-app limit ──────────────────
    from itertools import groupby

    rows_by_app: Dict[int, list] = {}
    for row in rows:
        rows_by_app.setdefault(row.app_id, []).append(row)

    for app_id, app_rows in rows_by_app.items():
        # Check existing count in app_keywords
        existing = (
            db.query(AppKeyword.id)
            .filter(AppKeyword.app_id == app_id)
            .count()
        )
        slots = max(0, _MAX_PER_APP - existing)
        if slots == 0:
            logger.debug(f"[Backfill] app {app_id} already at limit — skipping")
            continue

        # Sort by opportunity_score DESC to keep best keywords when truncating
        app_rows_sorted = sorted(
            app_rows, key=lambda r: r.opportunity_score or 0, reverse=True
        )[:slots]

        for row in app_rows_sorted:
            keyword_id = id_map.get(row.keyword)
            if keyword_id is None:
                continue

            # Insert into app_keywords
            try:
                stmt = (
                    pg_insert(AppKeyword.__table__)
                    .values(
                        app_id=app_id,
                        keyword_id=keyword_id,
                        rank=row.app_rank,
                        traffic=float(row.traffic_score or 0),
                        opportunity_score=float(row.opportunity_score or 0),
                        source=row.source or "backfill",
                        created_at=now,
                    )
                    .on_conflict_do_nothing(index_elements=["app_id", "keyword_id"])
                )
                result = db.execute(stmt)
                stats["app_keywords_inserted"] += result.rowcount or 0
            except Exception as exc:
                db.rollback()
                logger.error(
                    f"[Backfill] app_keywords insert failed "
                    f"(app={app_id}, kw={row.keyword!r}): {exc}"
                )
                continue

            # Upsert into keyword_metrics
            try:
                ins = pg_insert(KeywordMetrics.__table__).values(
                    keyword_id=keyword_id,
                    search_volume=int(row.search_volume or 0),
                    difficulty=float(row.difficulty or 0),
                    trend_score=0.0,
                    last_updated=now,
                )
                stmt = ins.on_conflict_do_update(
                    index_elements=["keyword_id"],
                    set_={
                        "search_volume": ins.excluded.search_volume,
                        "difficulty": ins.excluded.difficulty,
                        "last_updated": now,
                    },
                )
                db.execute(stmt)
                stats["metrics_upserted"] += 1
            except Exception as exc:
                db.rollback()
                logger.error(
                    f"[Backfill] keyword_metrics upsert failed for {row.keyword!r}: {exc}"
                )
                continue

        try:
            db.commit()
            stats["apps_processed"] += 1
        except Exception as exc:
            db.rollback()
            logger.error(f"[Backfill] commit failed for app {app_id}: {exc}")

    logger.info(
        f"[Backfill] Complete — "
        f"terms_inserted={stats['terms_inserted']}, "
        f"app_keywords_inserted={stats['app_keywords_inserted']}, "
        f"metrics_upserted={stats['metrics_upserted']}, "
        f"apps_processed={stats['apps_processed']}"
    )
    return stats
