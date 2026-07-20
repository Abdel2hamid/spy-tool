"""
Data retention / pruning service.

Rankings and reviews are append-only time series. Without pruning they grow
unbounded, inflating storage cost and slowing window queries. This module
provides safe, idempotent prune jobs:

  - Rankings older than the retention window are deleted.
  - Reviews older than the retention window are deleted.
  - Optionally keep a sampled heartbeat per app/chart/country/genre so that
    long-unchanged ranks still have a recent anchor.

All operations use indexed date columns and run in small batches to avoid
long-running transactions and table bloat.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Retention windows
_RANKING_RETENTION_DAYS = 90
_REVIEW_RETENTION_DAYS = 180

# Batch size for DELETE loops; keeps each transaction short.
_DELETE_BATCH = 5000


def prune_rankings(db: Session, retention_days: int = _RANKING_RETENTION_DAYS) -> int:
    """Delete ranking rows older than ``retention_days``. Returns rows deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    total = 0

    while True:
        # Delete in batches using the indexed recorded_at column.
        result = db.execute(
            text("""
                DELETE FROM rankings
                WHERE id IN (
                    SELECT id FROM rankings
                    WHERE recorded_at < :cutoff
                    ORDER BY id
                    LIMIT :batch
                )
            """),
            {"cutoff": cutoff, "batch": _DELETE_BATCH},
        )
        db.commit()
        rows = result.rowcount
        total += rows
        if rows < _DELETE_BATCH:
            break

    logger.info(f"[RETENTION] Pruned {total} ranking rows older than {retention_days} days")
    return total


def prune_reviews(db: Session, retention_days: int = _REVIEW_RETENTION_DAYS) -> int:
    """Delete review rows older than ``retention_days``. Returns rows deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    total = 0

    while True:
        result = db.execute(
            text("""
                DELETE FROM reviews
                WHERE id IN (
                    SELECT id FROM reviews
                    WHERE date < :cutoff
                    ORDER BY id
                    LIMIT :batch
                )
            """),
            {"cutoff": cutoff, "batch": _DELETE_BATCH},
        )
        db.commit()
        rows = result.rowcount
        total += rows
        if rows < _DELETE_BATCH:
            break

    logger.info(f"[RETENTION] Pruned {total} review rows older than {retention_days} days")
    return total


def prune_all(db: Session) -> Tuple[int, int]:
    """Run both prune jobs. Returns (rankings_deleted, reviews_deleted)."""
    rankings = prune_rankings(db)
    reviews = prune_reviews(db)
    return rankings, reviews
