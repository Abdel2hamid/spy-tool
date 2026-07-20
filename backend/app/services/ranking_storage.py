"""
Ranking storage helper.

Rankings are a high-volume time series. Writing a row on every scrape run
quickly produces duplicate rows for apps that have not moved, exploding
storage and slowing window queries. This module implements change-only
writes: a new row is inserted only when the rank changed or when the last
record is older than the heartbeat window.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Ranking

logger = logging.getLogger(__name__)

# Write a heartbeat row at most once per day even when the rank has not
# changed, so trending/staleness checks still see recent activity.
_HEARTBEAT_HOURS = 24


def record_ranking(
    db: Session,
    *,
    app_id: int,
    chart_type: str,
    rank: int,
    country: str = "us",
    genre: str = "all",
    category_id: Optional[int] = None,
    recorded_at: Optional[datetime] = None,
) -> Optional[Ranking]:
    """
    Insert a ranking row only if it is meaningfully new.

    A row is written when:
      - No prior ranking exists for this (app, chart, country, genre), or
      - The rank changed vs the most recent row, or
      - The most recent row is older than ``_HEARTBEAT_HOURS``.

    Returns the new Ranking row or None if suppressed as a duplicate.
    """
    country = (country or "us").lower()
    genre = genre or "all"
    now = recorded_at or datetime.now(timezone.utc)

    latest = (
        db.query(Ranking)
        .filter(
            Ranking.app_id == app_id,
            Ranking.chart_type == chart_type,
            Ranking.country == country,
            Ranking.genre == genre,
        )
        .order_by(Ranking.recorded_at.desc())
        .first()
    )

    if latest is not None:
        # Same rank and recent enough -> suppress duplicate write
        if latest.rank == rank:
            heartbeat_cutoff = now - timedelta(hours=_HEARTBEAT_HOURS)
            if latest.recorded_at and latest.recorded_at >= heartbeat_cutoff:
                return None

        previous_rank = latest.rank
        rank_velocity = (previous_rank - rank) if previous_rank is not None else 0
    else:
        previous_rank = None
        rank_velocity = 0

    ranking = Ranking(
        app_id=app_id,
        chart_type=chart_type,
        category_id=category_id,
        country=country,
        genre=genre,
        rank=rank,
        previous_rank=previous_rank,
        rank_velocity=rank_velocity,
        recorded_at=now,
    )
    db.add(ranking)
    return ranking
