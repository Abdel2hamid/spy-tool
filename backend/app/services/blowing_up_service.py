"""
Blowing Up Service
==================
Detects iOS apps showing unusually fast momentum across rankings and reviews.

An app is "blowing up" when it simultaneously exhibits:
  • rapid rank improvement (moving toward #1)
  • accelerating review velocity
  • consistent upward movement (not a single noisy spike)
  • presence across multiple chart types / categories
  • sufficient data confidence

Score formula (components, all 0–100):
  blowing_up_score =
      0.30 × rank_velocity_score
    + 0.25 × rank_change_score
    + 0.20 × reviews_velocity_score
    + 0.10 × chart_presence_score
    + 0.10 × cross_market_score
    + 0.05 × consistency_score

Then multiplied by confidence_factor (0–1) for data-quality adjustment.

Refreshed every 15 minutes by the blowing_up_compute scheduler job.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, exists as sa_exists
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.models import App, AppBlowingUpScore, Ranking, Review

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scoring weights (must sum to 1.0)
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "rank_velocity_score":    0.30,
    "rank_change_score":      0.25,
    "reviews_velocity_score": 0.20,
    "chart_presence_score":   0.10,
    "cross_market_score":     0.10,
    "consistency_score":      0.05,
}

# ---------------------------------------------------------------------------
# Timeframe map
# ---------------------------------------------------------------------------

_TIMEFRAME_DAYS = {"24h": 1, "3d": 3, "7d": 7}


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _norm_rank_velocity(avg_velocity: float) -> float:
    """
    Rank velocity = avg positions improved per ranking snapshot (positive = toward #1).
    0 → 0, 50+ → 100.
    """
    if avg_velocity <= 0:
        return 0.0
    return min(100.0, avg_velocity * 2.0)


def _norm_rank_change(rank_change: int, starting_rank: Optional[int]) -> float:
    """
    Normalise rank improvement relative to starting position.
    Uses the larger of (relative %, absolute / 100) to reward both
    large absolute jumps AND big relative climbs from deep ranks.
    """
    if rank_change <= 0 or not starting_rank or starting_rank <= 0:
        return 0.0
    relative = rank_change / starting_rank          # e.g. 50 / 100 = 0.50
    absolute = min(1.0, rank_change / 100)          # 100 positions = 1.0
    return min(100.0, max(relative, absolute) * 100)


def _norm_reviews_velocity(reviews_per_day: float) -> float:
    """0 reviews/day → 0, 10+ reviews/day → 100."""
    return min(100.0, reviews_per_day * 10.0)


def _norm_chart_presence(appearances: int, days: int) -> float:
    """
    Normalise chart snapshot count.
    Expect ≈ 3 chart types × days scrapes total in window; 1 appearance/day = 50.
    """
    if days <= 0:
        return 0.0
    daily_rate = appearances / days
    return min(100.0, daily_rate / 2.0 * 100)     # 2 appearances/day = 100


def _norm_cross_market(markets_count: int) -> float:
    """1 market = 20, 5+ markets = 100."""
    return min(100.0, markets_count * 20.0)


def _consistency(rankings_asc: list) -> float:
    """
    Fraction of consecutive snapshot pairs showing rank improvement (smaller = better).
    Returns 0–100.
    """
    if len(rankings_asc) < 2:
        return 0.0
    improvements = sum(
        1 for i in range(1, len(rankings_asc))
        if rankings_asc[i].rank < rankings_asc[i - 1].rank
    )
    return (improvements / (len(rankings_asc) - 1)) * 100


def _confidence(snapshot_count: int) -> float:
    """
    Data quality factor 0–1.
    < 2 snapshots → excluded upstream (candidate query guarantees ≥2).
    2–4  → penalised (× 0.6 scaling)  → range 0.12–0.24
    5–9  → scaling without penalty     → range 0.50–0.90
    10+  → 1.0

    NOTE: There is intentionally no hard floor here — the multiplier already
    downscores low-data apps naturally.  Removing the old `< 0.2` gate means
    apps with 2–3 snapshots are scored (with low blowing_up_score ≈ 5–15)
    rather than silently dropped.
    """
    if snapshot_count < 2:
        return 0.0
    raw = min(1.0, snapshot_count / 10.0)
    if snapshot_count < 5:
        raw *= 0.6
    return raw


# ---------------------------------------------------------------------------
# Badge & reason generators
# ---------------------------------------------------------------------------

def _badges(
    rank_change_score: float,
    reviews_velocity_score: float,
    markets_count: int,
    consistency_score: float,
    confidence_score: float,
    is_new_entry: bool,
) -> List[str]:
    b: List[str] = []
    if is_new_entry:
        b.append("New Entry")
    if rank_change_score >= 50:
        b.append("Rapid Climb")
    if reviews_velocity_score >= 40:
        b.append("Fast Reviews")
    if markets_count >= 3:
        b.append("Cross-Market")
    if consistency_score >= 70:
        b.append("Consistent Momentum")
    if confidence_score >= 80:
        b.append("High Confidence")
    return b


def _why_flagged(
    rank_change: int,
    starting_rank: Optional[int],
    current_rank: int,
    reviews_velocity: float,
    chart_appearances: int,
    markets_count: int,
    consistency_score: float,
    timeframe_days: int,
    snapshot_count: int,
) -> List[str]:
    reasons: List[str] = []
    if rank_change > 0 and starting_rank:
        reasons.append(
            f"Rank improved from #{starting_rank} to #{current_rank} over {timeframe_days}d"
        )
    if reviews_velocity >= 1.0:
        reasons.append(f"Growing at {reviews_velocity:.1f} new reviews/day")
    if chart_appearances >= 3:
        reasons.append(f"Appeared {chart_appearances}× in chart snapshots")
    if markets_count >= 3:
        reasons.append(f"Momentum across {markets_count} market segments")
    if consistency_score >= 60:
        reasons.append(
            f"Consistent upward movement ({consistency_score:.0f}% of snapshots improving)"
        )
    if snapshot_count >= 8:
        reasons.append(f"Strong data confidence ({snapshot_count} ranking snapshots)")
    return reasons or ["Accelerating rank velocity detected"]


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------

class BlowingUpService:
    """
    Computes and caches blowing-up scores following the same pattern as
    trending_compute_service.py (precomputed table, upserted on schedule).
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Single-app computation
    # ------------------------------------------------------------------

    def compute_for_app(
        self,
        app_id: int,
        timeframe_days: int = 7,
    ) -> Optional[Dict]:
        """
        Compute blowing_up_score for one app over *timeframe_days*.
        Returns None if there is insufficient data.
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(days=timeframe_days)

        # Ranking snapshots in window (oldest → newest for trajectory)
        rankings = (
            self.db.query(Ranking)
            .filter(
                Ranking.app_id == app_id,
                Ranking.recorded_at >= cutoff,
                Ranking.rank.isnot(None),
            )
            .order_by(Ranking.recorded_at.asc())
            .all()
        )

        if len(rankings) < 2:
            return None

        latest  = rankings[-1]
        first   = rankings[0]
        current_rank  = latest.rank
        starting_rank = first.rank

        # Was the app absent from charts before this window?
        pre_window_count = (
            self.db.query(func.count(Ranking.id))
            .filter(
                Ranking.app_id == app_id,
                Ranking.recorded_at < cutoff,
                Ranking.rank.isnot(None),
            )
            .scalar()
        ) or 0
        is_new_entry = (pre_window_count == 0)

        # Rank change (positive = moved toward #1)
        rank_change = starting_rank - current_rank

        # Average rank_velocity from snapshots (already stored per-row)
        velocities = [r.rank_velocity for r in rankings if r.rank_velocity is not None]
        avg_velocity = sum(velocities) / len(velocities) if velocities else 0.0

        # Review velocity
        review_count = (
            self.db.query(func.count(Review.id))
            .filter(Review.app_id == app_id, Review.date >= cutoff)
            .scalar()
        ) or 0
        reviews_velocity = review_count / max(timeframe_days, 1)

        # Chart presence & cross-market
        chart_types  = {r.chart_type   for r in rankings if r.chart_type}
        category_ids = {r.category_id  for r in rankings if r.category_id is not None}
        chart_appearances = len(rankings)
        markets_count     = len(chart_types) + len(category_ids)

        # Consistency
        consistency_score = _consistency(rankings)

        # Confidence — no hard gate; confidence acts as a natural score multiplier.
        # Apps with 2–3 snapshots will have low blowing_up_score (e.g. 5–15) which
        # correctly reflects limited data rather than being silently excluded.
        confidence_factor = _confidence(len(rankings))

        # Component scores
        rvs  = _norm_rank_velocity(avg_velocity)
        rcs  = _norm_rank_change(rank_change, starting_rank)
        revs = _norm_reviews_velocity(reviews_velocity)
        cps  = _norm_chart_presence(chart_appearances, timeframe_days)
        cms  = _norm_cross_market(markets_count)
        con  = consistency_score  # already 0-100

        composite = (
            _WEIGHTS["rank_velocity_score"]    * rvs  +
            _WEIGHTS["rank_change_score"]      * rcs  +
            _WEIGHTS["reviews_velocity_score"] * revs +
            _WEIGHTS["chart_presence_score"]   * cps  +
            _WEIGHTS["cross_market_score"]     * cms  +
            _WEIGHTS["consistency_score"]      * con
        )

        blowing_up_score = round(composite * confidence_factor, 2)
        confidence_score = round(confidence_factor * 100, 2)

        return {
            "app_id":               app_id,
            "blowing_up_score":     blowing_up_score,
            "rank_velocity_score":  round(rvs, 2),
            "rank_change_score":    round(rcs, 2),
            "reviews_velocity_score": round(revs, 2),
            "chart_presence_score": round(cps, 2),
            "cross_market_score":   round(cms, 2),
            "consistency_score":    round(con, 2),
            "confidence_score":     confidence_score,
            "rank_change":          rank_change,
            "rank_velocity":        round(avg_velocity, 2),
            "reviews_velocity":     round(reviews_velocity, 2),
            "chart_appearances":    chart_appearances,
            "markets_count":        markets_count,
            "badges": _badges(rcs, revs, markets_count, con, confidence_score, is_new_entry),
            "why_flagged": _why_flagged(
                rank_change, starting_rank, current_rank,
                reviews_velocity, chart_appearances, markets_count,
                con, timeframe_days, len(rankings),
            ),
        }

    # ------------------------------------------------------------------
    # Batch computation + persistence
    # ------------------------------------------------------------------

    def compute_for_all_apps(self, timeframe_days: int = 7) -> int:
        """
        Compute and persist blowing_up_score for all eligible apps.
        Returns the number of apps scored (inserted/updated).

        Commit strategy: per-app commit so that one bad row never rolls back
        the entire batch.
        """
        now    = datetime.utcnow()
        cutoff = now - timedelta(days=timeframe_days)

        # Candidate selection: apps with ≥ 2 ranking snapshots in the window
        app_ids = [
            row[0]
            for row in (
                self.db.query(Ranking.app_id)
                .filter(Ranking.recorded_at >= cutoff, Ranking.rank.isnot(None))
                .group_by(Ranking.app_id)
                .having(func.count(Ranking.id) >= 2)
                .all()
            )
        ]

        candidates = len(app_ids)
        logger.info(
            f"[BlowingUp] starting compute: {candidates} candidate apps "
            f"(timeframe={timeframe_days}d, cutoff={cutoff.date()})"
        )

        scored = 0
        skipped_no_data = 0
        failed = 0

        for app_id in app_ids:
            try:
                result = self.compute_for_app(app_id, timeframe_days)
                if result is None:
                    skipped_no_data += 1
                    continue

                stmt = (
                    pg_insert(AppBlowingUpScore)
                    .values(
                        app_id=app_id,
                        blowing_up_score=result["blowing_up_score"],
                        rank_velocity_score=result["rank_velocity_score"],
                        rank_change_score=result["rank_change_score"],
                        reviews_velocity_score=result["reviews_velocity_score"],
                        chart_presence_score=result["chart_presence_score"],
                        cross_market_score=result["cross_market_score"],
                        consistency_score=result["consistency_score"],
                        confidence_score=result["confidence_score"],
                        rank_change=result["rank_change"],
                        rank_velocity=result["rank_velocity"],
                        reviews_velocity=result["reviews_velocity"],
                        chart_appearances=result["chart_appearances"],
                        markets_count=result["markets_count"],
                        badges=result["badges"],
                        why_flagged=result["why_flagged"],
                        computed_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=["app_id"],
                        set_={
                            "blowing_up_score":       result["blowing_up_score"],
                            "rank_velocity_score":    result["rank_velocity_score"],
                            "rank_change_score":      result["rank_change_score"],
                            "reviews_velocity_score": result["reviews_velocity_score"],
                            "chart_presence_score":   result["chart_presence_score"],
                            "cross_market_score":     result["cross_market_score"],
                            "consistency_score":      result["consistency_score"],
                            "confidence_score":       result["confidence_score"],
                            "rank_change":            result["rank_change"],
                            "rank_velocity":          result["rank_velocity"],
                            "reviews_velocity":       result["reviews_velocity"],
                            "chart_appearances":      result["chart_appearances"],
                            "markets_count":          result["markets_count"],
                            "badges":                 result["badges"],
                            "why_flagged":            result["why_flagged"],
                            "computed_at":            now,
                        },
                    )
                )
                self.db.execute(stmt)
                # Commit per-app: prevents one bad row from rolling back the batch
                self.db.commit()
                scored += 1

            except Exception as exc:
                logger.warning(f"[BlowingUp] app_id={app_id} failed: {exc}")
                self.db.rollback()
                failed += 1

        logger.info(
            f"[BlowingUp] done: candidates={candidates} scored={scored} "
            f"skipped={skipped_no_data} failed={failed}"
        )
        return scored

    # ------------------------------------------------------------------
    # Query precomputed results
    # ------------------------------------------------------------------

    def get_blowing_up_apps(
        self,
        limit: int = 50,
        skip: int = 0,
        sort_by: str = "blowing_up_score",
        sort_order: str = "desc",
        min_confidence: float = 0.3,
        min_reviews_velocity: float = 0.0,
        category: Optional[str] = None,
        chart_type: Optional[str] = None,
    ) -> Tuple[List, int]:
        """
        Query the precomputed scores table with optional filters.
        Returns (rows, total) where each row is (AppBlowingUpScore, App).
        """
        query = (
            self.db.query(AppBlowingUpScore, App)
            .join(App, App.id == AppBlowingUpScore.app_id)
            .filter(
                AppBlowingUpScore.blowing_up_score > 0,
                AppBlowingUpScore.confidence_score >= min_confidence * 100,
            )
        )

        if min_reviews_velocity > 0:
            query = query.filter(
                AppBlowingUpScore.reviews_velocity >= min_reviews_velocity
            )

        if category:
            query = query.filter(App.primary_category.ilike(f"%{category}%"))

        if chart_type:
            cutoff = datetime.utcnow() - timedelta(days=7)
            query = query.filter(
                sa_exists().where(
                    (Ranking.app_id == AppBlowingUpScore.app_id)
                    & (Ranking.chart_type == chart_type)
                    & (Ranking.recorded_at >= cutoff)
                )
            )

        _SORT_MAP = {
            "blowing_up_score": AppBlowingUpScore.blowing_up_score,
            "rank_velocity":    AppBlowingUpScore.rank_velocity,
            "rank_change":      AppBlowingUpScore.rank_change,
            "reviews_velocity": AppBlowingUpScore.reviews_velocity,
            "confidence":       AppBlowingUpScore.confidence_score,
        }
        sort_col = _SORT_MAP.get(sort_by, AppBlowingUpScore.blowing_up_score)
        query = (
            query.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())
        )

        total = query.count()
        rows  = query.offset(skip).limit(limit).all()
        return rows, total
