"""
CampaignTrackingService
=======================
Pure signal engine for detecting and classifying app growth patterns.

Architecture role:
  SOURCE DATA   (Ranking, Review)               ← no direct scraping
  METRIC LAYER  (AppMetricSnapshot)             ← downloads delta
  AD LAYER      (AdCampaign)                    ← ad activity
  SCORE LAYER   (AppBlowingUpScore)             ← momentum signal
        ↓
  CampaignTrackingService                       ← signal classification
        ↓
  growth_events table                           ← persistent decision log

Event types:
  paid_push         — strong ad activity + rank/reviews surge
  organic_breakout  — rank/reviews surge, no ad evidence
  mixed             — both ad activity and organic signals
  momentum_surge    — unusual rank velocity without clear cause
  campaign_cooling  — previously active campaign, now decelerating
  unknown_unusual   — something significant but cause unclear

Rules:
  - Only creates a new GrowthEvent if the same event_type is not already
    active for the same app (avoids duplicate events).
  - Marks old events inactive when replaced by a newer classification.
  - Does NOT scrape anything — all data consumed from existing tables.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.models import (
    App, Ranking, Review, AppBlowingUpScore, AppTrendingScore,
    AdCampaign, AppMetricSnapshot, GrowthEvent,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
_MIN_RANK_VELOCITY      = 1.5    # rank_velocity to consider "significant movement"
_MIN_REVIEW_VELOCITY    = 1.5    # new reviews/day to consider "review surge"
_MIN_BU_SCORE           = 30.0   # blowing_up_score threshold for "momentum"
_MIN_RANK_CHANGE        = 15     # rank improved >= 15 positions → notable
_COOLING_DAYS           = 5      # look back N days to detect deceleration
_MIN_CONFIDENCE         = 0.30   # below this → skip (no clear signal)
_EVENT_DEDUP_HOURS      = 12     # don't create same event_type for same app within N hours


class CampaignTrackingService:
    """
    Classifies growth patterns for all apps showing signals.

    Usage (scheduler):
        svc = CampaignTrackingService(db)
        svc.run_for_all()

    Usage (single app):
        svc = CampaignTrackingService(db)
        events = svc.run_for_app(app_id)
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_for_all(self) -> Dict:
        """
        Run campaign detection for all apps showing signals above threshold.

        Batch-prefetch version: 6 batch queries total instead of ~6N per-app queries.
        """
        from collections import defaultdict
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        cutoff_7d = now - timedelta(days=7)
        cutoff_14d = now - timedelta(days=14)
        cutoff_30d = now - timedelta(days=30)

        # Candidate apps with blowing_up_score > threshold
        candidates = (
            self.db.query(App)
            .join(AppBlowingUpScore, AppBlowingUpScore.app_id == App.id)
            .filter(AppBlowingUpScore.blowing_up_score >= _MIN_BU_SCORE)
            .all()
        )
        if not candidates:
            return {"candidates": 0, "events_created": 0}

        app_ids = [a.id for a in candidates]

        # ── Batch prefetch 1: recent rankings (7 days) ────────────────────
        rankings_by_app = defaultdict(list)
        for row in (
            self.db.query(Ranking.app_id, Ranking.rank, Ranking.rank_velocity, Ranking.recorded_at)
            .filter(Ranking.app_id.in_(app_ids), Ranking.recorded_at >= cutoff_7d)
            .order_by(Ranking.recorded_at.desc())
            .all()
        ):
            rankings_by_app[row.app_id].append(row)

        # ── Batch prefetch 2: review counts (14 days) ─────────────────────
        review_counts = dict(
            self.db.query(Review.app_id, func.count(Review.id))
            .filter(Review.app_id.in_(app_ids), Review.date >= cutoff_14d)
            .group_by(Review.app_id)
            .all()
        )

        # ── Batch prefetch 3: blowing_up_scores ───────────────────────────
        bu_scores = {}
        for bu in (
            self.db.query(AppBlowingUpScore)
            .filter(AppBlowingUpScore.app_id.in_(app_ids))
            .all()
        ):
            bu_scores[bu.app_id] = bu

        # ── Batch prefetch 4: latest metric snapshots ─────────────────────
        # Subquery: max snapshot_at per app_id
        snap_sub = (
            self.db.query(
                AppMetricSnapshot.app_id,
                func.max(AppMetricSnapshot.snapshot_at).label("max_ts"),
            )
            .filter(AppMetricSnapshot.app_id.in_(app_ids))
            .group_by(AppMetricSnapshot.app_id)
            .subquery()
        )
        latest_snaps = {}
        for snap in (
            self.db.query(AppMetricSnapshot)
            .join(
                snap_sub,
                and_(
                    AppMetricSnapshot.app_id == snap_sub.c.app_id,
                    AppMetricSnapshot.snapshot_at == snap_sub.c.max_ts,
                ),
            )
            .all()
        ):
            latest_snaps[snap.app_id] = snap

        # ── Batch prefetch 5: active ad campaigns ─────────────────────────
        campaigns_by_app = defaultdict(list)
        for camp in (
            self.db.query(AdCampaign)
            .filter(AdCampaign.app_id.in_(app_ids), AdCampaign.status == "active")
            .all()
        ):
            campaigns_by_app[camp.app_id].append(camp)

        # ── Batch prefetch 6: oldest ranking per app (30 days) for start estimate
        oldest_rank_sub = (
            self.db.query(
                Ranking.app_id,
                func.min(Ranking.recorded_at).label("min_ts"),
            )
            .filter(Ranking.app_id.in_(app_ids), Ranking.recorded_at >= cutoff_30d)
            .group_by(Ranking.app_id)
            .subquery()
        )
        oldest_rankings = {}
        for row in (
            self.db.query(Ranking.app_id, Ranking.rank_velocity, Ranking.recorded_at)
            .join(
                oldest_rank_sub,
                and_(
                    Ranking.app_id == oldest_rank_sub.c.app_id,
                    Ranking.recorded_at == oldest_rank_sub.c.min_ts,
                ),
            )
            .all()
        ):
            oldest_rankings[row.app_id] = row

        # Also prefetch all rankings for 30d for start estimation
        rankings_30d_by_app = defaultdict(list)
        for row in (
            self.db.query(Ranking.app_id, Ranking.rank_velocity, Ranking.recorded_at)
            .filter(Ranking.app_id.in_(app_ids), Ranking.recorded_at >= cutoff_30d)
            .order_by(Ranking.recorded_at.asc())
            .all()
        ):
            rankings_30d_by_app[row.app_id].append(row)

        # ── Process each candidate using prefetched data (zero per-app queries)
        events_created = 0
        dedup_cutoff = now - timedelta(hours=_EVENT_DEDUP_HOURS)

        for app in candidates:
            try:
                signals = {}
                aid = app.id

                # Ranking signals
                recent = rankings_by_app.get(aid, [])
                if recent:
                    velocities = [r.rank_velocity or 0 for r in recent]
                    avg_velocity = sum(velocities) / len(velocities)
                    max_velocity = max(velocities)
                    ranks = [r.rank for r in recent if r.rank]
                    rank_change = (ranks[-1] - ranks[0]) if len(ranks) >= 2 else 0
                    signals["avg_rank_velocity"] = round(avg_velocity, 2)
                    signals["max_rank_velocity"] = round(max_velocity, 2)
                    signals["rank_change_7d"] = rank_change
                    signals["current_rank"] = ranks[0] if ranks else None

                # Review velocity
                rev_count = review_counts.get(aid, 0)
                signals["review_velocity_14d"] = round(rev_count / 14.0, 2)

                # Blowing Up Score
                bu = bu_scores.get(aid)
                if bu:
                    signals["blowing_up_score"] = bu.blowing_up_score
                    signals["rank_change_score"] = bu.rank_change_score or 0
                    signals["reviews_velocity_score"] = bu.reviews_velocity_score or 0
                    signals["cross_market_score"] = bu.cross_market_score or 0
                    signals["consistency_score"] = bu.consistency_score or 0

                # Metric Snapshot
                snap = latest_snaps.get(aid)
                if snap:
                    signals["estimated_downloads_max"] = snap.estimated_downloads_max
                    signals["install_confidence"] = snap.install_confidence

                # Ad Activity
                camps = campaigns_by_app.get(aid, [])
                signals["active_ad_campaigns"] = len(camps)
                signals["ad_networks"] = list({c.network for c in camps})
                signals["max_ad_confidence"] = (
                    max((c.campaign_confidence or 0 for c in camps), default=0.0)
                )

                # Skip if no interesting signals
                if (
                    signals.get("avg_rank_velocity", 0) < 0.5
                    and signals.get("review_velocity_14d", 0) < 0.5
                    and signals.get("blowing_up_score", 0) < 20
                    and signals.get("active_ad_campaigns", 0) == 0
                ):
                    continue

                # Classify
                event_type, confidence, explanation = self._classify(signals)
                if confidence < _MIN_CONFIDENCE:
                    continue

                # Dedup check
                existing = (
                    self.db.query(GrowthEvent)
                    .filter(
                        GrowthEvent.app_id == aid,
                        GrowthEvent.event_type == event_type,
                        GrowthEvent.detected_at >= dedup_cutoff,
                        GrowthEvent.active_status == True,
                    )
                    .first()
                )
                if existing:
                    continue

                # Deactivate old events
                self.db.query(GrowthEvent).filter(
                    GrowthEvent.app_id == aid,
                    GrowthEvent.active_status == True,
                ).update({"active_status": False}, synchronize_session=False)

                # Estimate start from prefetched 30d rankings
                started_at = None
                for r in rankings_30d_by_app.get(aid, []):
                    if (r.rank_velocity or 0) >= _MIN_RANK_VELOCITY:
                        started_at = r.recorded_at
                        break
                if started_at is None:
                    r30 = rankings_30d_by_app.get(aid, [])
                    if r30:
                        started_at = r30[0].recorded_at

                event = GrowthEvent(
                    app_id=aid,
                    detected_at=now,
                    event_type=event_type,
                    confidence=round(confidence, 2),
                    explanation=explanation,
                    signals=signals,
                    started_at_estimate=started_at,
                    active_status=True,
                )
                self.db.add(event)
                events_created += 1
            except Exception as exc:
                logger.warning(f"[campaign] Failed for app {app.app_id}: {exc}")

        self.db.commit()
        logger.info(f"[campaign] Created {events_created} growth events for {len(candidates)} candidates")
        return {"candidates": len(candidates), "events_created": events_created}

    def run_for_app(self, app_db_id: int) -> List[GrowthEvent]:
        """Classify growth signals for a single app. Returns list of new GrowthEvents."""
        app = self.db.query(App).filter(App.id == app_db_id).first()
        if not app:
            return []

        signals = self._gather_signals(app)
        if not signals:
            return []

        event_type, confidence, explanation = self._classify(signals)
        if confidence < _MIN_CONFIDENCE:
            return []

        # Dedup: don't insert same event_type within recent window
        dedup_cutoff = datetime.now(timezone.utc) - timedelta(hours=_EVENT_DEDUP_HOURS)
        existing = (
            self.db.query(GrowthEvent)
            .filter(
                GrowthEvent.app_id == app_db_id,
                GrowthEvent.event_type == event_type,
                GrowthEvent.detected_at >= dedup_cutoff,
                GrowthEvent.active_status == True,
            )
            .first()
        )
        if existing:
            return []  # already logged this event recently

        # Deactivate previous events of different types (new classification supersedes)
        self.db.query(GrowthEvent).filter(
            GrowthEvent.app_id == app_db_id,
            GrowthEvent.active_status == True,
        ).update({"active_status": False}, synchronize_session=False)

        # Estimate when this growth started
        started_at = self._estimate_start(app, signals)

        event = GrowthEvent(
            app_id=app_db_id,
            detected_at=datetime.now(timezone.utc),
            event_type=event_type,
            confidence=round(confidence, 2),
            explanation=explanation,
            signals=signals,
            started_at_estimate=started_at,
            active_status=True,
        )
        self.db.add(event)
        return [event]

    def get_events(
        self,
        app_db_id: Optional[int] = None,
        event_type: Optional[str] = None,
        active_only: bool = True,
        limit: int = 50,
    ) -> List[GrowthEvent]:
        q = self.db.query(GrowthEvent)
        if app_db_id:
            q = q.filter(GrowthEvent.app_id == app_db_id)
        if event_type:
            q = q.filter(GrowthEvent.event_type == event_type)
        if active_only:
            q = q.filter(GrowthEvent.active_status == True)
        return q.order_by(GrowthEvent.detected_at.desc()).limit(limit).all()

    # ------------------------------------------------------------------
    # Signal gathering
    # ------------------------------------------------------------------

    def _gather_signals(self, app: App) -> Dict:
        """Collect all available signals for classification into a dict."""
        signals: Dict = {}

        # ── Ranking signals ─────────────────────────────────────────────
        cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)
        recent_rankings = (
            self.db.query(Ranking)
            .filter(Ranking.app_id == app.id, Ranking.recorded_at >= cutoff_7d)
            .order_by(Ranking.recorded_at.desc())
            .all()
        )
        if recent_rankings:
            velocities = [r.rank_velocity or 0 for r in recent_rankings]
            avg_velocity = sum(velocities) / len(velocities)
            max_velocity = max(velocities)
            ranks = [r.rank for r in recent_rankings if r.rank]
            rank_change = 0
            if len(ranks) >= 2:
                rank_change = ranks[-1] - ranks[0]  # positive = improved (lower rank #)
            signals["avg_rank_velocity"] = round(avg_velocity, 2)
            signals["max_rank_velocity"] = round(max_velocity, 2)
            signals["rank_change_7d"] = rank_change
            signals["current_rank"] = ranks[0] if ranks else None

        # ── Review velocity ─────────────────────────────────────────────
        cutoff_14d = datetime.now(timezone.utc) - timedelta(days=14)
        recent_reviews = (
            self.db.query(Review)
            .filter(Review.app_id == app.id, Review.date >= cutoff_14d)
            .count()
        )
        signals["review_velocity_14d"] = round(recent_reviews / 14.0, 2)

        # ── Blowing Up Score ────────────────────────────────────────────
        bu = self.db.query(AppBlowingUpScore).filter(AppBlowingUpScore.app_id == app.id).first()
        if bu:
            signals["blowing_up_score"] = bu.blowing_up_score
            signals["rank_change_score"] = bu.rank_change_score or 0
            signals["reviews_velocity_score"] = bu.reviews_velocity_score or 0
            signals["cross_market_score"] = bu.cross_market_score or 0
            signals["consistency_score"] = bu.consistency_score or 0

        # ── Metric Snapshot ─────────────────────────────────────────────
        latest_snap = (
            self.db.query(AppMetricSnapshot)
            .filter(AppMetricSnapshot.app_id == app.id)
            .order_by(AppMetricSnapshot.snapshot_at.desc())
            .first()
        )
        if latest_snap:
            signals["estimated_downloads_max"] = latest_snap.estimated_downloads_max
            signals["install_confidence"] = latest_snap.install_confidence

        # ── Ad Activity ─────────────────────────────────────────────────
        active_campaigns = (
            self.db.query(AdCampaign)
            .filter(AdCampaign.app_id == app.id, AdCampaign.status == "active")
            .all()
        )
        signals["active_ad_campaigns"] = len(active_campaigns)
        signals["ad_networks"] = list({c.network for c in active_campaigns})
        if active_campaigns:
            signals["max_ad_confidence"] = max(c.campaign_confidence or 0 for c in active_campaigns)
        else:
            signals["max_ad_confidence"] = 0.0

        # Skip if there's truly nothing interesting
        if (
            signals.get("avg_rank_velocity", 0) < 0.5
            and signals.get("review_velocity_14d", 0) < 0.5
            and signals.get("blowing_up_score", 0) < 20
            and signals.get("active_ad_campaigns", 0) == 0
        ):
            return {}

        return signals

    # ------------------------------------------------------------------
    # Classification engine
    # ------------------------------------------------------------------

    def _classify(self, signals: Dict) -> Tuple[str, float, str]:
        """
        Classify signals into an event_type with confidence.
        Returns (event_type, confidence, explanation).
        """
        rank_vel = signals.get("avg_rank_velocity", 0)
        rank_change = signals.get("rank_change_7d", 0)
        rev_vel = signals.get("review_velocity_14d", 0)
        bu_score = signals.get("blowing_up_score", 0)
        ad_campaigns = signals.get("active_ad_campaigns", 0)
        ad_confidence = signals.get("max_ad_confidence", 0.0)
        cross_market = signals.get("cross_market_score", 0)

        has_strong_momentum = bu_score >= _MIN_BU_SCORE or (
            rank_vel >= _MIN_RANK_VELOCITY and rank_change >= _MIN_RANK_CHANGE
        )
        has_review_surge = rev_vel >= _MIN_REVIEW_VELOCITY
        has_ad_activity = ad_campaigns > 0 and ad_confidence >= 0.30
        has_strong_ad = ad_confidence >= 0.50

        # ── Classification rules (priority order) ───────────────────────
        if has_strong_ad and has_strong_momentum and has_review_surge:
            # All signals fire: paid ads driving installs + organic reviews
            event_type = "paid_push"
            confidence = min(0.9, 0.5 + (ad_confidence * 0.3) + (0.1 if cross_market >= 30 else 0))
            explanation = (
                f"Strong paid activity detected ({ad_campaigns} network(s), confidence {ad_confidence:.0%}). "
                f"Rank improved {rank_change} positions, {rev_vel:.1f} reviews/day. "
                f"Consistent with an active UA campaign."
            )

        elif has_strong_momentum and has_review_surge and not has_ad_activity:
            # Organic signals only: the app is legitimately blowing up
            event_type = "organic_breakout"
            confidence = min(0.85, 0.4 + (bu_score / 100 * 0.4) + (0.05 if rank_change >= 30 else 0))
            explanation = (
                f"Strong organic momentum: rank improved {rank_change} positions, "
                f"{rev_vel:.1f} reviews/day, blowing-up score {bu_score:.0f}. "
                f"No ad signals detected — growth appears organic."
            )

        elif has_strong_ad and has_strong_momentum:
            # Ads running + rank improving, but review surge not confirmed
            event_type = "mixed"
            confidence = min(0.80, 0.4 + (ad_confidence * 0.25) + (0.10 if has_review_surge else 0))
            explanation = (
                f"Paid activity ({ad_campaigns} network(s)) combined with rank momentum "
                f"({rank_vel:.1f} velocity, {rank_change} change). Growth has both "
                f"paid and organic components."
            )

        elif has_strong_momentum and not has_review_surge and not has_ad_activity:
            # Rank moving fast but no other confirmation
            event_type = "momentum_surge"
            confidence = min(0.65, 0.30 + (rank_vel / 20 * 0.25))
            explanation = (
                f"Unusual rank momentum: velocity {rank_vel:.1f}, change {rank_change} positions. "
                f"Insufficient review or ad evidence to classify cause."
            )

        elif has_ad_activity and not has_strong_momentum:
            # Ads without rank improvement → likely campaign cooling
            event_type = "campaign_cooling"
            confidence = min(0.60, 0.30 + ad_confidence * 0.2)
            explanation = (
                f"Ad activity detected ({ad_campaigns} network(s)) but rank momentum is low "
                f"(velocity {rank_vel:.1f}). Campaign may be losing effectiveness."
            )

        else:
            event_type = "unknown_unusual"
            confidence = min(0.45, 0.2 + (bu_score / 100 * 0.25))
            explanation = (
                f"Signals present but pattern unclear. "
                f"BU score {bu_score:.0f}, rank velocity {rank_vel:.1f}, "
                f"{rev_vel:.1f} reviews/day."
            )

        return event_type, confidence, explanation

    # ------------------------------------------------------------------
    # Start time estimation
    # ------------------------------------------------------------------

    def _estimate_start(self, app: App, signals: Dict) -> Optional[datetime]:
        """
        Estimate when this growth event started by walking backward through
        ranking history to find where velocity first exceeded threshold.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        rankings = (
            self.db.query(Ranking)
            .filter(Ranking.app_id == app.id, Ranking.recorded_at >= cutoff)
            .order_by(Ranking.recorded_at.asc())
            .all()
        )
        if not rankings:
            return None

        # Walk forward; find first rank_velocity above threshold
        for r in rankings:
            if (r.rank_velocity or 0) >= _MIN_RANK_VELOCITY:
                return r.recorded_at

        return rankings[0].recorded_at if rankings else None
