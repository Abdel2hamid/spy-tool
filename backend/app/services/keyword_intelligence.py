"""
Keyword Intelligence Service
=============================
Analyses keyword_search_snapshots to determine:

  • Which keywords drive an app's ranking
  • Organic vs Sponsored placement breakdown
  • Primary keyword (highest-scoring)
  • Traffic mix estimate (organic% vs ads%)

Scoring formula per (app, keyword) pair:
  score = position_pts * recency_weight * frequency_weight
          + organic_bonus - sponsored_penalty

Position points:
  Rank 1       → 50 pts
  Rank 2-3     → 35 pts
  Rank 4-10    → 20 pts
  Rank 11-20   → 10 pts

Organic bonus  = +15 when NOT sponsored
Sponsored pen. = -10 when sponsored

Recency weight = 1.0 (last 24 h) → 0.5 (7 days old)
Frequency weight = number of times seen / max_seen across keywords
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import App, AppKeyword, Keyword, KeywordSearchSnapshot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

_POSITION_PTS = {
    1: 50,
    2: 35,
    3: 35,
}


def _position_points(rank: int) -> int:
    if rank == 1:
        return 50
    if rank <= 3:
        return 35
    if rank <= 10:
        return 20
    return 10


ORGANIC_BONUS = 15
SPONSORED_PENALTY = 10


def _recency_weight(captured_at: datetime) -> float:
    """1.0 for <24 h old, linearly degrades to 0.5 at 7 days."""
    now = datetime.now(timezone.utc)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    age_hours = (now - captured_at).total_seconds() / 3600
    if age_hours <= 24:
        return 1.0
    if age_hours >= 7 * 24:
        return 0.5
    # Linear interpolation
    return 1.0 - (0.5 * (age_hours - 24) / (7 * 24 - 24))


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------

class KeywordIntelligenceService:
    def __init__(self, db: Session, lookback_days: int = 30):
        self.db = db
        self.lookback_days = lookback_days

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_app_intelligence(self, app_id_str: str) -> Optional[Dict]:
        """
        Return full keyword intelligence for one app (by App Store string ID).
        Returns None if the app is not in the DB or has no snapshots.
        """
        app = self.db.query(App).filter(App.app_id == app_id_str).first()
        if not app:
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        snapshots = (
            self.db.query(KeywordSearchSnapshot)
            .filter(
                KeywordSearchSnapshot.app_id == app_id_str,
                KeywordSearchSnapshot.captured_at >= cutoff,
            )
            .order_by(KeywordSearchSnapshot.captured_at.desc())
            .all()
        )

        if not snapshots:
            # Fall back to AppKeyword data if no snapshots yet
            return self._fallback_from_app_keywords(app)

        return self._compute_intelligence(app, snapshots)

    def get_intelligence_by_db_id(self, db_id: int) -> Optional[Dict]:
        """Convenience: look up by DB integer primary key."""
        app = self.db.query(App).filter(App.id == db_id).first()
        if not app:
            return None
        return self.get_app_intelligence(app.app_id)

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    def _compute_intelligence(self, app: App, snapshots: List) -> Dict:
        # Group snapshots by keyword
        keyword_data: Dict[str, Dict] = {}

        for snap in snapshots:
            kw = snap.keyword
            if kw not in keyword_data:
                keyword_data[kw] = {
                    "keyword": kw,
                    "best_position": snap.position,
                    "best_organic_position": snap.organic_position,
                    "is_sponsored_any": snap.is_sponsored,
                    "is_organic_any": not snap.is_sponsored,
                    "appearances": 0,
                    "scores": [],
                    "last_seen": snap.captured_at,
                }
            entry = keyword_data[kw]

            # Track best (lowest) positions
            entry["best_position"] = min(entry["best_position"], snap.position)
            if snap.organic_position:
                bp = entry.get("best_organic_position") or 999
                entry["best_organic_position"] = min(bp, snap.organic_position)

            if snap.is_sponsored:
                entry["is_sponsored_any"] = True
            else:
                entry["is_organic_any"] = True

            entry["appearances"] += 1
            entry["last_seen"] = max(entry["last_seen"], snap.captured_at)

            # Per-snapshot score contribution
            pos = snap.organic_position or snap.position
            pts = _position_points(pos)
            rw = _recency_weight(snap.captured_at)
            bonus = ORGANIC_BONUS if not snap.is_sponsored else -SPONSORED_PENALTY
            entry["scores"].append(pts * rw + bonus)

        if not keyword_data:
            return self._fallback_from_app_keywords(app)

        # Frequency weight normalization
        max_appearances = max(d["appearances"] for d in keyword_data.values()) or 1

        # Compute final score per keyword
        scored = []
        for kw, d in keyword_data.items():
            freq_w = d["appearances"] / max_appearances
            raw_score = sum(d["scores"])
            final_score = raw_score * freq_w
            scored.append((final_score, kw, d))

        scored.sort(reverse=True, key=lambda x: x[0])

        # Enrich with Keyword table data (search_volume, difficulty)
        kw_meta = self._get_keyword_meta([kw for _, kw, _ in scored])

        # Build output lists
        organic_keywords = []
        ads_keywords = []

        for _, kw, d in scored[:20]:
            meta = kw_meta.get(kw, {})
            if d["is_organic_any"]:
                organic_keywords.append({
                    "keyword": kw,
                    "rank": d.get("best_organic_position") or d["best_position"],
                    "search_volume": meta.get("search_volume", 0),
                    "difficulty": meta.get("difficulty", 0.0),
                })
            if d["is_sponsored_any"]:
                ads_keywords.append({
                    "keyword": kw,
                    "position": d["best_position"],
                })

        # Primary keyword = top organic or top overall
        primary_keyword = None
        confidence = 0
        if organic_keywords:
            primary_keyword = organic_keywords[0]["keyword"]
            best_score = scored[0][0]
            confidence = min(int(best_score), 100)
        elif ads_keywords:
            primary_keyword = ads_keywords[0]["keyword"]
            confidence = 30

        # Traffic mix
        n_organic = len(organic_keywords)
        n_ads = len(ads_keywords)
        total = n_organic + n_ads or 1
        organic_pct = round(n_organic / total * 100)
        ads_pct = 100 - organic_pct

        last_scanned = max((s.captured_at for s in snapshots), default=None)

        return {
            "app_id": app.app_id,
            "app_name": app.name,
            "primary_keyword": primary_keyword,
            "confidence": confidence,
            "organic_keywords": organic_keywords,
            "ads_keywords": ads_keywords,
            "traffic_mix": {"organic": organic_pct, "ads": ads_pct},
            "total_snapshots": len(snapshots),
            "last_scanned": last_scanned,
        }

    def _fallback_from_app_keywords(self, app: App) -> Dict:
        """Use existing AppKeyword rows when no snapshots exist yet."""
        app_keywords = (
            self.db.query(AppKeyword, Keyword)
            .join(Keyword, Keyword.id == AppKeyword.keyword_id)
            .filter(AppKeyword.app_id == app.id)
            .order_by(AppKeyword.position.asc().nullslast())
            .limit(10)
            .all()
        )

        organic_keywords = []
        for ak, kw in app_keywords:
            organic_keywords.append({
                "keyword": kw.term,
                "rank": ak.position or 0,
                "search_volume": kw.search_volume or 0,
                "difficulty": kw.difficulty or 0.0,
            })

        primary_keyword = organic_keywords[0]["keyword"] if organic_keywords else None

        return {
            "app_id": app.app_id,
            "app_name": app.name,
            "primary_keyword": primary_keyword,
            "confidence": 30,  # low confidence — no real scan data
            "organic_keywords": organic_keywords,
            "ads_keywords": [],
            "traffic_mix": {"organic": 100, "ads": 0},
            "total_snapshots": 0,
            "last_scanned": None,
        }

    def _get_keyword_meta(self, terms: List[str]) -> Dict[str, Dict]:
        if not terms:
            return {}
        rows = (
            self.db.query(Keyword)
            .filter(Keyword.term.in_(terms))
            .all()
        )
        return {r.term: {"search_volume": r.search_volume, "difficulty": r.difficulty} for r in rows}

    # ------------------------------------------------------------------
    # Traffic source estimation (batch, for all apps with snapshot data)
    # ------------------------------------------------------------------

    def compute_traffic_sources_all(self) -> List[Dict]:
        """
        Return a traffic-source summary for every app that has snapshot data.
        Used by analytics / dashboard.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)

        # Get distinct apps with snapshots
        rows = (
            self.db.query(KeywordSearchSnapshot.app_id)
            .filter(KeywordSearchSnapshot.captured_at >= cutoff)
            .distinct()
            .all()
        )

        summaries = []
        for (app_id_str,) in rows:
            intel = self.get_app_intelligence(app_id_str)
            if intel:
                summaries.append({
                    "app_id": app_id_str,
                    "app_name": intel["app_name"],
                    "organic_percent": intel["traffic_mix"]["organic"],
                    "ads_percent": intel["traffic_mix"]["ads"],
                    "primary_keyword": intel["primary_keyword"],
                })

        summaries.sort(key=lambda x: x["organic_percent"], reverse=True)
        return summaries
