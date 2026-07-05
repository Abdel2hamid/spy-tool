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
import math
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.models import App, AppBlowingUpScore, Ranking, Review
from app.utils.batch_utils import log_memory

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


def _norm_reviews_velocity(reviews_per_day: float, total_reviews: int = 0) -> float:
    """
    Log-scaled review velocity with incumbent dampening.

    Uses log scaling so a breakout gaining 5 reviews/day and a giant gaining
    50/day are not separated by 10× in score:
      1/day  →  ~42    5/day  →  ~81    10/day → 100

    Then dampens apps with large lifetime review bases (incumbents):
      ≤ 500 total reviews  → no dampening
      500k+ total reviews  → 80 % dampening

    This prevents YouTube / TikTok / Netflix from monopolising the list via
    sheer review volume while small breakout apps stay competitive.
    """
    if reviews_per_day <= 0:
        return 0.0
    base = min(100.0, math.log1p(reviews_per_day) / math.log(11.0) * 100.0)
    if total_reviews <= 500:
        return base
    dampening = min(0.80, math.log10(total_reviews / 500.0) * 0.35)
    return base * (1.0 - dampening)


def _incumbent_penalty(total_reviews: int) -> float:
    """
    Final-score multiplier (0.10 – 1.0) that penalises giant incumbents.

    Apps with < 10 000 lifetime reviews : no penalty  (1.0)
    Apps with   1 000 000+ reviews      : 90 % penalty (0.10)

    Ensures YouTube / TikTok / Netflix cannot dominate the blowing-up list
    even when they happen to be showing momentum signals.
    """
    if total_reviews <= 10_000:
        return 1.0
    dampening = min(0.90, math.log10(total_reviews / 10_000) * 0.45)
    return max(0.10, 1.0 - dampening)


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


def _stability_score(rankings: list) -> float:
    """
    Fraction of consecutive snapshot pairs where the rank value changed (0–1).
    High value = rank was actively moving = reliable, informative signal.
    """
    if len(rankings) < 2:
        return 0.0
    changes = sum(
        1 for i in range(1, len(rankings))
        if rankings[i].rank != rankings[i - 1].rank
    )
    return changes / (len(rankings) - 1)


def _confidence(
    snapshot_count: int,
    days_tracked: float,
    stability_score: float,
    total_reviews: int,
) -> float:
    """
    Multi-signal confidence factor (0–1).

    Components:
      coverage_score  = min(1, snapshot_count / 10)    — breadth of ranking history
      time_score      = min(1, days_tracked / 7)       — window spans ≥ 1 week
      stability_score = fraction of snapshots with rank changes (0–1)
      reviews_score   = min(1, total_reviews / 100)    — review depth

    Formula:
      confidence = 0.4 × coverage + 0.3 × time + 0.2 × stability + 0.1 × reviews

    Floor: apps with ≥ 2 snapshots always get at least 0.1 so they are never
    filtered out by a default min_confidence threshold of 0.
    """
    if snapshot_count < 2:
        return 0.0

    coverage_score = min(1.0, snapshot_count / 10.0)
    time_score     = min(1.0, max(0.0, days_tracked) / 7.0)
    stab_score     = min(1.0, max(0.0, float(stability_score)))
    reviews_score  = min(1.0, total_reviews / 100.0)

    confidence = (
        0.4 * coverage_score +
        0.3 * time_score +
        0.2 * stab_score +
        0.1 * reviews_score
    )

    return max(confidence, 0.1)


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
        country: str = "us",
    ) -> Optional[Dict]:
        """
        Compute blowing_up_score for one app over *timeframe_days*.
        Returns None if there is insufficient data.
        """
        country = (country or "us").lower()
        now    = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=timeframe_days)

        # Ranking snapshots in window (oldest → newest for trajectory)
        rankings = (
            self.db.query(Ranking)
            .filter(
                Ranking.app_id == app_id,
                Ranking.country == country,
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
                Ranking.country == country,
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

        # Lifetime reviews — used for incumbent dampening
        current_reviews = (
            self.db.query(App.current_reviews).filter(App.id == app_id).scalar()
        ) or 0

        # Chart presence & cross-market
        chart_types  = {r.chart_type   for r in rankings if r.chart_type}
        category_ids = {r.category_id  for r in rankings if r.category_id is not None}
        chart_appearances = len(rankings)
        markets_count     = len(chart_types) + len(category_ids)

        # Consistency
        consistency_score = _consistency(rankings)

        # Confidence — 4-signal weighted formula; floor of 0.1 for ≥2 snapshots
        days_tracked      = (
            (rankings[-1].recorded_at - rankings[0].recorded_at).total_seconds() / 86400.0
        )
        confidence_factor = _confidence(
            snapshot_count=len(rankings),
            days_tracked=days_tracked,
            stability_score=_stability_score(rankings),
            total_reviews=review_count,
        )

        # Component scores
        rvs  = _norm_rank_velocity(avg_velocity)
        rcs  = _norm_rank_change(rank_change, starting_rank)
        revs = _norm_reviews_velocity(reviews_velocity, current_reviews)
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

        penalty = _incumbent_penalty(current_reviews)
        blowing_up_score = round(composite * confidence_factor * penalty, 2)
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
    # Prefetch-based scoring (used by batch path)
    # ------------------------------------------------------------------

    def _compute_from_prefetch(
        self,
        app_id: int,
        rankings: list,
        review_count: int,
        is_new_entry: bool,
        timeframe_days: int,
        now: datetime,
        current_reviews: int = 0,
    ) -> Optional[Dict]:
        """
        Compute score for one app using pre-fetched data (no DB access).
        Returns None if there is insufficient data (< 2 ranking snapshots).
        """
        if len(rankings) < 2:
            return None

        latest       = rankings[-1]
        first        = rankings[0]
        current_rank = latest.rank
        starting_rank = first.rank

        rank_change  = starting_rank - current_rank

        velocities   = [r.rank_velocity for r in rankings if r.rank_velocity is not None]
        avg_velocity = sum(velocities) / len(velocities) if velocities else 0.0

        reviews_velocity = review_count / max(timeframe_days, 1)

        chart_types      = {r.chart_type  for r in rankings if r.chart_type}
        category_ids     = {r.category_id for r in rankings if r.category_id is not None}
        chart_appearances = len(rankings)
        markets_count     = len(chart_types) + len(category_ids)

        consistency_score = _consistency(rankings)

        # Confidence — 4-signal weighted formula; floor of 0.1 for ≥2 snapshots
        days_tracked      = (
            (rankings[-1].recorded_at - rankings[0].recorded_at).total_seconds() / 86400.0
        )
        confidence_factor = _confidence(
            snapshot_count=len(rankings),
            days_tracked=days_tracked,
            stability_score=_stability_score(rankings),
            total_reviews=review_count,
        )

        rvs  = _norm_rank_velocity(avg_velocity)
        rcs  = _norm_rank_change(rank_change, starting_rank)
        revs = _norm_reviews_velocity(reviews_velocity, current_reviews)
        cps  = _norm_chart_presence(chart_appearances, timeframe_days)
        cms  = _norm_cross_market(markets_count)
        con  = consistency_score

        composite = (
            _WEIGHTS["rank_velocity_score"]    * rvs  +
            _WEIGHTS["rank_change_score"]      * rcs  +
            _WEIGHTS["reviews_velocity_score"] * revs +
            _WEIGHTS["chart_presence_score"]   * cps  +
            _WEIGHTS["cross_market_score"]     * cms  +
            _WEIGHTS["consistency_score"]      * con
        )

        penalty = _incumbent_penalty(current_reviews)
        blowing_up_score = round(composite * confidence_factor * penalty, 2)
        confidence_score = round(confidence_factor * 100, 2)

        return {
            "app_id":                 app_id,
            "blowing_up_score":       blowing_up_score,
            "rank_velocity_score":    round(rvs, 2),
            "rank_change_score":      round(rcs, 2),
            "reviews_velocity_score": round(revs, 2),
            "chart_presence_score":   round(cps, 2),
            "cross_market_score":     round(cms, 2),
            "consistency_score":      round(con, 2),
            "confidence_score":       confidence_score,
            "rank_change":            rank_change,
            "rank_velocity":          round(avg_velocity, 2),
            "reviews_velocity":       round(reviews_velocity, 2),
            "chart_appearances":      chart_appearances,
            "markets_count":          markets_count,
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

    def compute_for_all_apps(
        self,
        timeframe_days: int = 7,
        max_apps: int = 500,
        country: str = "us",
    ) -> int:
        """
        Compute and persist blowing_up_score for all eligible apps.

        Processes candidates in batches of 50 to bound memory usage —
        rankings are only prefetched for the current batch, then committed
        and expired before the next batch.

        Returns the number of apps scored (inserted/updated).
        """
        country = (country or "us").lower()
        t0 = time.monotonic()
        log_memory("blowing_up", "start")
        now    = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=timeframe_days)

        # ── 1. Candidates: apps with ≥2 snapshots, ordered by rank improvement ──
        rank_improvement_expr = (
            func.max(Ranking.rank) - func.min(Ranking.rank)
        ).label("rank_improvement")

        candidate_rows = (
            self.db.query(
                Ranking.app_id,
                func.count(Ranking.id).label("cnt"),
                rank_improvement_expr,
            )
            .filter(
                Ranking.country == country,
                Ranking.recorded_at >= cutoff,
                Ranking.rank.isnot(None),
            )
            .group_by(Ranking.app_id)
            .having(func.count(Ranking.id) >= 2)
            .order_by(rank_improvement_expr.desc())
            .limit(max_apps)
            .all()
        )
        app_ids = [row[0] for row in candidate_rows]
        candidates = len(app_ids)

        logger.info(
            "[BlowingUp] starting compute: %d candidate apps "
            "(country=%s, timeframe=%dd, max_apps=%d, cutoff=%s)",
            candidates, country, timeframe_days, max_apps, cutoff.date(),
        )

        if not app_ids:
            logger.info(
                "[BlowingUp] no candidates for country=%s — done in %.2fs",
                country, time.monotonic() - t0,
            )
            return 0

        # ── Process in batches of 50 to bound memory ──
        _PREFETCH_BATCH = 50
        scored = 0
        skipped_no_data = 0
        failed = 0

        for i in range(0, len(app_ids), _PREFETCH_BATCH):
            batch_ids = app_ids[i : i + _PREFETCH_BATCH]

            # Prefetch rankings only for this batch
            all_rankings = (
                self.db.query(Ranking)
                .filter(
                    Ranking.app_id.in_(batch_ids),
                    Ranking.country == country,
                    Ranking.recorded_at >= cutoff,
                    Ranking.rank.isnot(None),
                )
                .order_by(Ranking.app_id, Ranking.recorded_at.asc())
                .all()
            )
            rankings_by_app: Dict[int, List] = defaultdict(list)
            for r in all_rankings:
                rankings_by_app[r.app_id].append(r)

            review_count_rows = (
                self.db.query(Review.app_id, func.count(Review.id).label("cnt"))
                .filter(Review.app_id.in_(batch_ids), Review.date >= cutoff)
                .group_by(Review.app_id)
                .all()
            )
            review_counts: Dict[int, int] = {row[0]: row[1] for row in review_count_rows}

            pre_window_apps = set(
                row[0]
                for row in (
                    self.db.query(Ranking.app_id)
                    .filter(
                        Ranking.app_id.in_(batch_ids),
                        Ranking.country == country,
                        Ranking.recorded_at < cutoff,
                        Ranking.rank.isnot(None),
                    )
                    .distinct()
                    .all()
                )
            )

            current_reviews_by_app: Dict[int, int] = {
                row[0]: (row[1] or 0)
                for row in (
                    self.db.query(App.id, App.current_reviews)
                    .filter(App.id.in_(batch_ids))
                    .all()
                )
            }

            # Score each app in this batch
            for app_id in batch_ids:
                try:
                    result = self._compute_from_prefetch(
                        app_id=app_id,
                        rankings=rankings_by_app.get(app_id, []),
                        review_count=review_counts.get(app_id, 0),
                        is_new_entry=(app_id not in pre_window_apps),
                        timeframe_days=timeframe_days,
                        now=now,
                        current_reviews=current_reviews_by_app.get(app_id, 0),
                    )
                    if result is None:
                        skipped_no_data += 1
                        continue

                    stmt = (
                        pg_insert(AppBlowingUpScore)
                        .values(
                            app_id=result["app_id"],
                            country=country,
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
                            index_elements=["app_id", "country"],
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
                    scored += 1
                except Exception as exc:
                    logger.warning("[BlowingUp] app_id=%s scoring failed: %s", app_id, exc)
                    failed += 1

            # Commit and release ORM objects after each batch
            try:
                self.db.commit()
            except Exception as exc:
                logger.error("[BlowingUp] batch commit failed: %s", exc)
                self.db.rollback()
            self.db.expire_all()

        log_memory("blowing_up", "end")
        elapsed = time.monotonic() - t0
        logger.info(
            "[BlowingUp] done in %.2fs: country=%s candidates=%d scored=%d "
            "skipped=%d failed=%d",
            elapsed, country, candidates, scored, skipped_no_data, failed,
        )
        return scored

    # ------------------------------------------------------------------
    # Multi-country batch computation
    # ------------------------------------------------------------------

    def compute_for_all_countries(
        self,
        timeframe_days: int = 7,
        max_apps: int = 500,
    ) -> int:
        """
        Compute and persist blowing_up_score for every storefront (country)
        that has recent ranking data, plus 'us' as a baseline.

        Returns the total number of (app, country) scores written across all
        countries.
        """
        now    = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=timeframe_days)

        rows = self.db.execute(
            text("SELECT DISTINCT country FROM rankings WHERE recorded_at >= :cutoff"),
            {"cutoff": cutoff},
        ).all()
        countries = sorted(
            {(row[0] or "us").lower() for row in rows if row[0]} | {"us"}
        )

        logger.info(
            "[BlowingUp] computing across %d countries: %s",
            len(countries), countries,
        )

        total = 0
        for cc in countries:
            total += self.compute_for_all_apps(
                timeframe_days=timeframe_days,
                max_apps=max_apps,
                country=cc,
            )

        logger.info(
            "[BlowingUp] all countries done: %d countries, %d total scores",
            len(countries), total,
        )
        return total

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
        country: str = "us",
    ) -> Tuple[List, int]:
        """
        Query the precomputed scores table with optional filters.
        Returns (rows, total) where each row is (AppBlowingUpScore, App).
        """
        country = (country or "us").lower()
        query = (
            self.db.query(AppBlowingUpScore, App)
            .join(App, App.id == AppBlowingUpScore.app_id)
            .filter(
                AppBlowingUpScore.country == country,
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
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            chart_subq = (
                self.db.query(Ranking.app_id)
                .filter(
                    Ranking.chart_type == chart_type,
                    Ranking.recorded_at >= cutoff,
                )
                .distinct()
                .subquery()
            )
            query = query.join(chart_subq, AppBlowingUpScore.app_id == chart_subq.c.app_id)

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
