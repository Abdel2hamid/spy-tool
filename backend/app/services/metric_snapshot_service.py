"""
MetricSnapshotService
=====================
Orchestrates install + revenue estimation into a unified time-series snapshot.

Architecture role:
  SOURCE DATA (App, Ranking, Review)
        ↓
  InstallEstimator  →  RevenueEstimator    (calculators — unchanged)
        ↓
  MetricSnapshotService                    (orchestrator + persistence)
        ↓
  app_metric_snapshots table               (shared backbone)
        ↓
  CampaignTrackingService / API endpoints  (consumers)

Rules:
- One snapshot per app per compute cycle (written by scheduler hourly).
- Also back-fills App.estimated_installs_*/estimated_revenue_* for backward compat.
- Snapshots are retained for 90 days; older rows pruned automatically.
- The `has_ads_signal` and `campaign_confidence` fields are populated later
  by AdIntelligenceService + CampaignTrackingService (UPDATE, not INSERT).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.models import App, AppMetricSnapshot
from app.services.install_estimator import InstallEstimator
from app.services.revenue_estimator import RevenueEstimator

logger = logging.getLogger(__name__)

_SNAPSHOT_RETENTION_DAYS = 90


class MetricSnapshotService:
    """
    Unified compute + persist layer for download and revenue estimates.

    Usage (scheduler / scoring worker):
        svc = MetricSnapshotService(db)
        svc.compute_all()

    Usage (on-demand for single app):
        svc = MetricSnapshotService(db)
        snap = svc.compute_for_app(app)
    """

    def __init__(self, db: Session):
        self.db = db
        self._install_est = InstallEstimator(db)
        self._revenue_est = RevenueEstimator(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_for_app(self, app: App) -> AppMetricSnapshot:
        """Compute a new metric snapshot for a single App ORM object."""
        install_result = self._install_est._compute(app)
        revenue_result = self._revenue_est._compute_from_installs(
            app,
            install_result["estimated_installs_min"],
            install_result["estimated_installs_max"],
        )

        install_confidence = install_result["install_confidence"]

        # Revenue confidence: never exceeds install confidence
        rev_confidence = install_confidence * 0.9
        if revenue_result["model"] == "free_ads_only":
            rev_confidence *= 0.7   # ad revenue is harder to estimate

        snap = AppMetricSnapshot(
            app_id=app.id,
            snapshot_at=datetime.now(timezone.utc),
            estimated_downloads_min=install_result["estimated_installs_min"],
            estimated_downloads_max=install_result["estimated_installs_max"],
            install_confidence=install_confidence,
            estimated_revenue_monthly_min=revenue_result["estimated_revenue_monthly_min"],
            estimated_revenue_monthly_max=revenue_result["estimated_revenue_monthly_max"],
            revenue_confidence=round(rev_confidence, 2),
            monetization_model=revenue_result["model"],
            has_ads_signal=False,    # updated later by AdIntelligenceService
            campaign_confidence=0.0,  # updated later by CampaignTrackingService
            source_signals={
                "review_count": app.current_reviews,
                "current_rank": app.current_rank,
                "category": app.primary_category,
                "methodology": install_result["methodology"],
            },
        )
        self.db.add(snap)

        # Back-fill cached columns on App for backward compat
        app.estimated_installs_min = install_result["estimated_installs_min"]
        app.estimated_installs_max = install_result["estimated_installs_max"]
        app.install_confidence = install_confidence
        app.estimated_revenue_monthly_min = revenue_result["estimated_revenue_monthly_min"]
        app.estimated_revenue_monthly_max = revenue_result["estimated_revenue_monthly_max"]

        return snap

    def compute_all(self) -> int:
        """
        Compute and persist metric snapshots for all tracked apps.
        Returns count of snapshots written.
        """
        apps = self.db.query(App).all()
        count = 0
        for app in apps:
            try:
                self.compute_for_app(app)
                count += 1
            except Exception as exc:
                logger.warning(f"[metric_snapshot] Failed for app {app.app_id}: {exc}")

        self.db.commit()
        self._prune_old_snapshots()
        logger.info(f"[metric_snapshot] Wrote {count} snapshots")
        return count

    def latest_snapshot(self, app_id: int) -> Optional[AppMetricSnapshot]:
        """Return the most recent snapshot for an app (by DB integer id)."""
        return (
            self.db.query(AppMetricSnapshot)
            .filter(AppMetricSnapshot.app_id == app_id)
            .order_by(AppMetricSnapshot.snapshot_at.desc())
            .first()
        )

    def snapshot_history(self, app_id: int, days: int = 30) -> list:
        """Return snapshots for the last N days for trend charts."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            self.db.query(AppMetricSnapshot)
            .filter(
                AppMetricSnapshot.app_id == app_id,
                AppMetricSnapshot.snapshot_at >= cutoff,
            )
            .order_by(AppMetricSnapshot.snapshot_at.asc())
            .all()
        )

    def downloads_delta(self, app_id: int, days: int = 7) -> Dict:
        """
        Compare latest snapshot vs snapshot from ~N days ago.
        Returns delta dict consumed by CampaignTrackingService.
        """
        now_snap = self.latest_snapshot(app_id)
        if not now_snap:
            return {"delta_min": 0, "delta_max": 0, "change_pct": 0.0}

        cutoff = now_snap.snapshot_at - timedelta(days=days)
        older = (
            self.db.query(AppMetricSnapshot)
            .filter(
                AppMetricSnapshot.app_id == app_id,
                AppMetricSnapshot.snapshot_at <= cutoff,
            )
            .order_by(AppMetricSnapshot.snapshot_at.desc())
            .first()
        )
        if not older:
            return {"delta_min": 0, "delta_max": 0, "change_pct": 0.0}

        delta_min = (now_snap.estimated_downloads_min or 0) - (older.estimated_downloads_min or 0)
        delta_max = (now_snap.estimated_downloads_max or 0) - (older.estimated_downloads_max or 0)
        base = (older.estimated_downloads_max or 1)
        change_pct = round((delta_max / base) * 100, 1) if base else 0.0

        return {"delta_min": delta_min, "delta_max": delta_max, "change_pct": change_pct}

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def _prune_old_snapshots(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=_SNAPSHOT_RETENTION_DAYS)
        deleted = (
            self.db.query(AppMetricSnapshot)
            .filter(AppMetricSnapshot.snapshot_at < cutoff)
            .delete(synchronize_session=False)
        )
        if deleted:
            self.db.commit()
            logger.info(f"[metric_snapshot] Pruned {deleted} old snapshots (>{_SNAPSHOT_RETENTION_DAYS}d)")
