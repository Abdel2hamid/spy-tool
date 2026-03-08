"""
Keyword History Service
=======================
Queries keyword_search_snapshots to produce a rank-over-time timeline
for a given app + keyword combination.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import KeywordSearchSnapshot

logger = logging.getLogger(__name__)


class KeywordHistoryService:
    def __init__(self, db: Session):
        self.db = db

    def get_history(
        self,
        app_id: str,
        keyword: str,
        country: str = "us",
        days: int = 90,
    ) -> Dict:
        """
        Return rank history for an app/keyword pair.

        Returns:
            {
                "app_id": str,
                "keyword": str,
                "country": str,
                "history": [{"date": "YYYY-MM-DD", "best_rank": int, "is_sponsored": bool}],
                "current_rank": int | None,
                "total_days": int,
            }
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        rows = (
            self.db.query(
                func.date(KeywordSearchSnapshot.captured_at).label("date"),
                func.min(KeywordSearchSnapshot.position).label("best_rank"),
                func.bool_or(KeywordSearchSnapshot.is_sponsored).label("is_sponsored"),
            )
            .filter(
                KeywordSearchSnapshot.app_id == app_id,
                KeywordSearchSnapshot.keyword == keyword,
                KeywordSearchSnapshot.country == country,
                KeywordSearchSnapshot.captured_at >= cutoff,
            )
            .group_by(func.date(KeywordSearchSnapshot.captured_at))
            .order_by(func.date(KeywordSearchSnapshot.captured_at))
            .all()
        )

        history = [
            {
                "date": str(row.date),
                "best_rank": row.best_rank,
                "is_sponsored": bool(row.is_sponsored),
            }
            for row in rows
        ]

        current_rank = history[-1]["best_rank"] if history else None

        return {
            "app_id": app_id,
            "keyword": keyword,
            "country": country,
            "history": history,
            "current_rank": current_rank,
            "total_days": len(history),
        }

    def get_all_keywords_for_app(self, app_id: str, country: str = "us") -> List[str]:
        """Return all keywords this app has appeared in, sorted by most recent."""
        rows = (
            self.db.query(KeywordSearchSnapshot.keyword)
            .filter(
                KeywordSearchSnapshot.app_id == app_id,
                KeywordSearchSnapshot.country == country,
            )
            .distinct()
            .all()
        )
        return [r.keyword for r in rows]
