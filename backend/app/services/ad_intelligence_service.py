"""
AdIntelligenceService
=====================
Detects ad activity for selected candidate apps.

Architecture role:
  SOURCE DATA (AppBlowingUpScore, AppTrendingScore, Ranking, KeywordSearchSnapshot)
        ↓
  Candidate selection  — only apps showing meaningful signals
        ↓
  Ad detection heuristics + optional provider adapters
        ↓
  AdCreative + AdCampaign tables

Design principles:
  - NEVER scan all apps blindly.
  - Candidates are selected from apps already flagged by existing signals.
  - Detection uses two layers:
      1. Heuristic inference from existing data (keyword position patterns,
         rank acceleration, review velocity spikes).
      2. Provider adapters (pluggable; currently: Apple Search Ads heuristic,
         Meta Ads Library public API).
  - Deduplication by (app_id, network, external_creative_id).
  - first_seen_at is never overwritten; last_seen_at updated on every run.

Signal mapping:
  - Apple Search Ads: inferred from keyword_search_snapshots + ranking acceleration
  - Meta (Facebook/Instagram): scraped from Meta Ads Library (public endpoint)
  - Google UAC: inferred from cross-market rank correlation
"""

import hashlib
import logging
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.models import (
    App, AppBlowingUpScore, AppTrendingScore, Ranking,
    KeywordSearchSnapshot, AdCreative, AdCampaign, AppMetricSnapshot,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Candidate selection thresholds
# ---------------------------------------------------------------------------
_MIN_BLOWING_UP_SCORE    = 35.0   # must be showing momentum
_MIN_RANK_CHANGE         = 10     # rank improved at least 10 positions
_MAX_CANDIDATE_APPS      = 200    # cap to avoid overwhelming any APIs
_SPONSORED_WINDOW_DAYS   = 14     # look back N days for keyword sponsored flags

# ---------------------------------------------------------------------------
# Heuristic thresholds
# ---------------------------------------------------------------------------
_APPLE_SA_VELOCITY_THRESHOLD = 2.0    # rank_velocity > 2 → Apple Search Ads signal
_APPLE_SA_KEYWORD_MIN_APPS   = 3      # app appears in ≥3 keyword snapshots → search ads likely
_META_ADS_URL                = "https://graph.facebook.com/v19.0/ads_archive"
_META_MIN_ACTIVE_DAYS        = 3      # creative seen for ≥3 days → call active


class AdIntelligenceService:
    """
    Main entry point for the Ad Intelligence domain.

    Usage (scheduler):
        svc = AdIntelligenceService(db)
        svc.run_for_candidates()

    Usage (on-demand for single app from detail page):
        svc = AdIntelligenceService(db)
        svc.run_for_app(app_id)
    """

    def __init__(self, db: Session, meta_access_token: Optional[str] = None):
        self.db = db
        self._meta_token = meta_access_token   # None → Meta layer skipped

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_for_candidates(self) -> Dict:
        """Select candidate apps and run full ad intelligence pipeline."""
        candidates = self._select_candidates()
        logger.info(f"[ad_intel] Selected {len(candidates)} candidate apps")

        total_creatives = 0
        total_campaigns = 0

        for app in candidates:
            try:
                c, camp = self._process_app(app)
                total_creatives += c
                total_campaigns += camp
            except Exception as exc:
                logger.warning(f"[ad_intel] Failed for app {app.app_id}: {exc}")

        self.db.commit()
        return {
            "candidates": len(candidates),
            "creatives_upserted": total_creatives,
            "campaigns_upserted": total_campaigns,
        }

    def run_for_app(self, app_db_id: int) -> Dict:
        """On-demand run for a single app (triggered from app detail view)."""
        app = self.db.query(App).filter(App.id == app_db_id).first()
        if not app:
            return {"error": "app not found"}
        c, camp = self._process_app(app)
        self.db.commit()
        return {"creatives_upserted": c, "campaigns_upserted": camp}

    def get_creatives(self, app_db_id: int) -> List[AdCreative]:
        return (
            self.db.query(AdCreative)
            .filter(AdCreative.app_id == app_db_id)
            .order_by(AdCreative.last_seen_at.desc())
            .all()
        )

    def get_campaigns(self, app_db_id: int) -> List[AdCampaign]:
        return (
            self.db.query(AdCampaign)
            .filter(AdCampaign.app_id == app_db_id)
            .order_by(AdCampaign.last_seen_at.desc())
            .all()
        )

    def has_active_campaign(self, app_db_id: int) -> bool:
        return (
            self.db.query(AdCampaign)
            .filter(AdCampaign.app_id == app_db_id, AdCampaign.status == "active")
            .count()
        ) > 0

    # ------------------------------------------------------------------
    # Candidate selection
    # ------------------------------------------------------------------

    def _select_candidates(self) -> List[App]:
        """
        Select apps worth running ad intelligence on.
        Priority:
          1. Apps with high blowing_up_score (showing unusual momentum)
          2. Apps with strong rank change in last 7 days
          3. Apps with high trending score
        """
        candidates: List[App] = []
        seen_ids = set()

        # Layer 1: Blowing up apps
        blowing_up = (
            self.db.query(App)
            .join(AppBlowingUpScore, AppBlowingUpScore.app_id == App.id)
            .filter(AppBlowingUpScore.blowing_up_score >= _MIN_BLOWING_UP_SCORE)
            .order_by(AppBlowingUpScore.blowing_up_score.desc())
            .limit(_MAX_CANDIDATE_APPS // 2)
            .all()
        )
        for app in blowing_up:
            if app.id not in seen_ids:
                candidates.append(app)
                seen_ids.add(app.id)

        # Layer 2: Apps with strong rank improvement (recent Ranking rows)
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        high_velocity = (
            self.db.query(App)
            .join(Ranking, Ranking.app_id == App.id)
            .filter(
                Ranking.recorded_at >= cutoff,
                Ranking.rank_velocity >= _APPLE_SA_VELOCITY_THRESHOLD,
            )
            .order_by(Ranking.rank_velocity.desc())
            .limit(_MAX_CANDIDATE_APPS // 2)
            .all()
        )
        for app in high_velocity:
            if app.id not in seen_ids and len(candidates) < _MAX_CANDIDATE_APPS:
                candidates.append(app)
                seen_ids.add(app.id)

        # Layer 3: High trending score fill-up
        if len(candidates) < _MAX_CANDIDATE_APPS // 2:
            trending = (
                self.db.query(App)
                .join(AppTrendingScore, AppTrendingScore.app_id == App.id)
                .filter(AppTrendingScore.trend_score >= 50.0)
                .order_by(AppTrendingScore.trend_score.desc())
                .limit(_MAX_CANDIDATE_APPS // 4)
                .all()
            )
            for app in trending:
                if app.id not in seen_ids and len(candidates) < _MAX_CANDIDATE_APPS:
                    candidates.append(app)
                    seen_ids.add(app.id)

        return candidates[:_MAX_CANDIDATE_APPS]

    # ------------------------------------------------------------------
    # Per-app processing
    # ------------------------------------------------------------------

    def _process_app(self, app: App) -> Tuple[int, int]:
        """Run all ad detection layers for one app. Returns (creatives, campaigns)."""
        creatives_count = 0
        campaigns_count = 0

        # Layer 1: Apple Search Ads heuristic
        apple_signals = self._detect_apple_search_ads(app)
        if apple_signals:
            c, camp = self._upsert_campaign(
                app=app,
                network="apple_search_ads",
                campaign_key=f"asa_{app.app_id}",
                confidence=apple_signals["confidence"],
                countries=["us"],
                creatives=apple_signals.get("creatives", []),
            )
            creatives_count += c
            campaigns_count += camp

        # Layer 2: Meta Ads Library (if token available)
        if self._meta_token:
            meta_signals = self._fetch_meta_ads(app)
            for campaign_data in meta_signals:
                c, camp = self._upsert_campaign(
                    app=app,
                    network="meta",
                    campaign_key=campaign_data["campaign_key"],
                    confidence=campaign_data["confidence"],
                    countries=campaign_data.get("countries", []),
                    creatives=campaign_data.get("creatives", []),
                )
                creatives_count += c
                campaigns_count += camp

        # Layer 3: Google UAC heuristic (cross-market rank correlation)
        goog_signals = self._detect_google_uac(app)
        if goog_signals:
            c, camp = self._upsert_campaign(
                app=app,
                network="google_uac",
                campaign_key=f"uac_{app.app_id}",
                confidence=goog_signals["confidence"],
                countries=goog_signals.get("countries", []),
                creatives=[],
            )
            creatives_count += c
            campaigns_count += camp

        return creatives_count, campaigns_count

    # ------------------------------------------------------------------
    # Detection heuristics
    # ------------------------------------------------------------------

    def _detect_apple_search_ads(self, app: App) -> Optional[Dict]:
        """
        Infer Apple Search Ads activity from:
        1. Keyword search snapshots showing the app at position 1-2 repeatedly.
        2. High rank_velocity in recent Ranking rows.
        3. BlowingUp score with rank_change_score component.

        Returns dict with confidence + synthetic creative data, or None.
        """
        confidence = 0.0

        # Signal A: keyword search snapshot frequency (sponsored positions)
        cutoff = datetime.now(timezone.utc) - timedelta(days=_SPONSORED_WINDOW_DAYS)
        snapshot_count = (
            self.db.query(KeywordSearchSnapshot)
            .filter(
                KeywordSearchSnapshot.app_id == str(app.app_id),
                KeywordSearchSnapshot.captured_at >= cutoff,
                KeywordSearchSnapshot.position <= 3,  # top-3 organic or sponsored slot
            )
            .count()
        )
        if snapshot_count >= _APPLE_SA_KEYWORD_MIN_APPS:
            confidence += 0.35

        # Signal B: rank_velocity spike in last 7 days
        cutoff7 = datetime.now(timezone.utc) - timedelta(days=7)
        max_velocity = (
            self.db.query(Ranking.rank_velocity)
            .filter(
                Ranking.app_id == app.id,
                Ranking.recorded_at >= cutoff7,
            )
            .order_by(Ranking.rank_velocity.desc())
            .first()
        )
        if max_velocity and (max_velocity[0] or 0) >= _APPLE_SA_VELOCITY_THRESHOLD:
            velocity_score = min((max_velocity[0] / 20.0), 1.0)  # normalise to 0-1
            confidence += 0.30 * velocity_score

        # Signal C: BlowingUp score (rank_change_score component)
        bu = (
            self.db.query(AppBlowingUpScore)
            .filter(AppBlowingUpScore.app_id == app.id)
            .first()
        )
        if bu and (bu.rank_change_score or 0) >= 50:
            confidence += 0.20

        # Signal D: reviews velocity spike (ads drive reviews)
        if bu and (bu.reviews_velocity_score or 0) >= 40:
            confidence += 0.15

        confidence = round(min(confidence, 1.0), 2)
        if confidence < 0.25:
            return None

        # Synthetic creative (no real creative URL available from heuristic)
        creative_id = hashlib.md5(f"asa_{app.app_id}_search".encode()).hexdigest()[:16]
        creatives = [
            {
                "external_creative_id": creative_id,
                "network": "apple_search_ads",
                "format": "search_result",
                "title": app.name,
                "body": app.subtitle or "",
                "cta": "Download",
                "creative_url": None,
                "preview_url": app.icon_url,
                "landing_url": app.url or f"https://apps.apple.com/app/id{app.app_id}",
                "raw_payload": {
                    "inferred": True,
                    "snapshot_count": snapshot_count,
                    "max_velocity": max_velocity[0] if max_velocity else 0,
                    "rank_change_score": bu.rank_change_score if bu else 0,
                },
            }
        ]
        return {"confidence": confidence, "creatives": creatives}

    def _detect_google_uac(self, app: App) -> Optional[Dict]:
        """
        Infer Google UAC by cross-market rank correlation.
        If the app ranks well across multiple chart types simultaneously,
        Google UAC (which drives installs across multiple networks) is likely.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        chart_types = (
            self.db.query(Ranking.chart_type)
            .filter(Ranking.app_id == app.id, Ranking.recorded_at >= cutoff)
            .distinct()
            .all()
        )
        distinct_charts = len(chart_types)
        if distinct_charts < 2:
            return None

        bu = (
            self.db.query(AppBlowingUpScore)
            .filter(AppBlowingUpScore.app_id == app.id)
            .first()
        )
        cross_market_score = (bu.cross_market_score or 0) if bu else 0

        confidence = 0.0
        if distinct_charts >= 2:
            confidence += 0.25
        if distinct_charts >= 3:
            confidence += 0.20
        if cross_market_score >= 40:
            confidence += 0.25
        if app.current_rank and app.current_rank <= 50:
            confidence += 0.15

        confidence = round(min(confidence, 0.75), 2)  # UAC is harder to confirm; cap lower
        if confidence < 0.30:
            return None

        return {
            "confidence": confidence,
            "countries": ["us", "gb", "au", "ca"],
        }

    def _fetch_meta_ads(self, app: App) -> List[Dict]:
        """
        Query Meta Ads Library public API for the app name.
        Returns list of campaign dicts.
        Requires FACEBOOK_ACCESS_TOKEN env var / config.
        """
        if not self._meta_token:
            return []

        try:
            params = urllib.parse.urlencode({
                "search_terms": app.name,
                "ad_type": "ALL",
                "ad_reached_countries": '["US"]',
                "limit": 10,
                "fields": "id,ad_creative_bodies,ad_creative_link_captions,ad_delivery_start_time,ad_delivery_stop_time,page_name,publisher_platforms",
                "access_token": self._meta_token,
            })
            url = f"{_META_ADS_URL}?{params}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except Exception as exc:
            logger.debug(f"[ad_intel] Meta API error for {app.name}: {exc}")
            return []

        ads = data.get("data", [])
        if not ads:
            return []

        # Group by page_name → one campaign per page
        campaigns: Dict[str, Dict] = {}
        for ad in ads:
            page = ad.get("page_name", "unknown")
            campaign_key = hashlib.md5(f"meta_{app.app_id}_{page}".encode()).hexdigest()[:16]

            if campaign_key not in campaigns:
                campaigns[campaign_key] = {
                    "campaign_key": campaign_key,
                    "confidence": 0.7,
                    "countries": ["us"],
                    "creatives": [],
                }

            body = (ad.get("ad_creative_bodies") or [""])[0]
            caption = (ad.get("ad_creative_link_captions") or [""])[0]
            cid = ad.get("id", "")
            campaigns[campaign_key]["creatives"].append({
                "external_creative_id": cid,
                "network": "meta",
                "format": "feed",
                "title": caption or app.name,
                "body": body,
                "cta": "Install",
                "creative_url": None,
                "preview_url": None,
                "landing_url": app.url or f"https://apps.apple.com/app/id{app.app_id}",
                "raw_payload": ad,
            })

        return list(campaigns.values())

    # ------------------------------------------------------------------
    # Upsert helpers
    # ------------------------------------------------------------------

    def _upsert_campaign(
        self,
        app: App,
        network: str,
        campaign_key: str,
        confidence: float,
        countries: List[str],
        creatives: List[Dict],
    ) -> Tuple[int, int]:
        """Upsert an AdCampaign and its AdCreatives. Returns (creatives_upserted, 1)."""
        now = datetime.now(timezone.utc)

        # Campaign upsert
        existing_campaign = (
            self.db.query(AdCampaign)
            .filter(
                AdCampaign.app_id == app.id,
                AdCampaign.network == network,
                AdCampaign.campaign_key == campaign_key,
            )
            .first()
        )
        if existing_campaign:
            existing_campaign.last_seen_at = now
            existing_campaign.status = "active"
            existing_campaign.campaign_confidence = confidence
            existing_campaign.countries = countries
            existing_campaign.active_creatives_count = len(creatives)
        else:
            existing_campaign = AdCampaign(
                app_id=app.id,
                network=network,
                campaign_key=campaign_key,
                first_seen_at=now,
                last_seen_at=now,
                active_creatives_count=len(creatives),
                countries=countries,
                status="active",
                campaign_confidence=confidence,
            )
            self.db.add(existing_campaign)

        # Creative upserts
        creatives_written = 0
        for cr in creatives:
            ext_id = cr.get("external_creative_id") or hashlib.md5(
                f"{app.app_id}_{network}_{cr.get('title','')}".encode()
            ).hexdigest()[:24]

            existing_cr = (
                self.db.query(AdCreative)
                .filter(
                    AdCreative.app_id == app.id,
                    AdCreative.network == network,
                    AdCreative.external_creative_id == ext_id,
                )
                .first()
            )
            if existing_cr:
                existing_cr.last_seen_at = now
                existing_cr.is_active = True
            else:
                new_cr = AdCreative(
                    app_id=app.id,
                    network=cr.get("network", network),
                    external_creative_id=ext_id,
                    format=cr.get("format"),
                    creative_url=cr.get("creative_url"),
                    preview_url=cr.get("preview_url"),
                    title=cr.get("title"),
                    body=cr.get("body"),
                    cta=cr.get("cta"),
                    landing_url=cr.get("landing_url"),
                    first_seen_at=now,
                    last_seen_at=now,
                    is_active=True,
                    raw_payload=cr.get("raw_payload"),
                )
                self.db.add(new_cr)
                creatives_written += 1

        # Mark stale creatives inactive (not seen in this run)
        seen_ids = {
            (cr.get("external_creative_id") or "")
            for cr in creatives
        }
        stale = (
            self.db.query(AdCreative)
            .filter(
                AdCreative.app_id == app.id,
                AdCreative.network == network,
                AdCreative.is_active == True,
                AdCreative.last_seen_at < now - timedelta(days=7),
            )
            .all()
        )
        for s in stale:
            if s.external_creative_id not in seen_ids:
                s.is_active = False

        return creatives_written, 1
