"""
Keyword Intelligence Pipeline

Multi-layer keyword enrichment system combining:
  1. Google Trends          — trend_score, trend_growth, trend_velocity, weekly sparklines
  2. Apple App Store signals — apps_count, dominance_score (via iTunes Search API)
  3. DataForSEO (optional)  — real search_volume, keyword_difficulty, cpc
  4. Unified scoring        — opportunity_score, feasibility_score

Configuration (via .env):
  GOOGLE_TRENDS_ENABLED=true       # set false if Google blocks pytrends
  DATAFORSEO_ENABLED=true          # requires credentials below
  DATAFORSEO_USERNAME=login@...
  DATAFORSEO_PASSWORD=yourpass
"""

import asyncio
import logging
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta
from math import log10
from typing import Dict, List, Optional

import httpx
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.models import Keyword, AppKeyword, KeywordTrend, App
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed keyword pools (one per App Store category)
# These are added to the DB on first pipeline run and enrich keyword discovery.
# ---------------------------------------------------------------------------
_CATEGORY_SEEDS: Dict[str, List[str]] = {
    "productivity": [
        "productivity app", "task manager", "to-do list", "notes app",
        "focus timer", "habit tracker", "calendar app", "time blocking",
        "pomodoro timer", "goal tracker",
    ],
    "health": [
        "fitness app", "workout tracker", "meditation app", "mental health app",
        "sleep tracker", "calorie counter", "yoga app", "running tracker",
        "weight loss app", "water tracker",
    ],
    "finance": [
        "budget app", "expense tracker", "investment app", "savings app",
        "money manager", "stock tracker", "crypto wallet", "bill tracker",
        "financial planner", "net worth tracker",
    ],
    "education": [
        "language learning app", "flashcard app", "study app", "kids learning app",
        "coding tutorial", "math practice", "reading app", "vocabulary app",
        "quiz app", "typing practice",
    ],
    "social": [
        "dating app", "friend finder app", "social networking app",
        "community app", "anonymous chat app", "pen pal app",
    ],
    "utilities": [
        "vpn app", "password manager", "qr code scanner", "pdf reader",
        "file manager", "document scanner", "clipboard manager",
        "screen recorder", "system cleaner",
    ],
    "ai": [
        "ai assistant app", "ai chat app", "ai writing app", "ai image generator",
        "voice assistant app", "chatbot app", "ai tutor", "ai journal",
        "ai meal planner", "ai personal trainer",
    ],
    "business": [
        "crm app", "invoicing app", "time tracking app", "project management app",
        "team collaboration", "remote work app", "expense report app",
        "contract app", "hr app",
    ],
    "photo": [
        "photo editor app", "camera app", "video editor app", "collage maker",
        "selfie editor", "background remover", "photo organizer",
    ],
    "games": [
        "casual game", "puzzle game", "word game", "trivia game",
        "strategy game", "idle game", "brain training game",
    ],
    "travel": [
        "travel planner app", "trip organizer", "flight tracker",
        "hotel finder", "language translator", "offline maps",
    ],
    "food": [
        "recipe app", "meal planner app", "food diary", "restaurant finder",
        "grocery list app", "cooking app", "intermittent fasting app",
    ],
}

_SEED_KEYWORDS = [kw for kws in _CATEGORY_SEEDS.values() for kw in kws]

# Time-to-live before re-fetching Google Trends for a keyword
_TRENDS_TTL_HOURS = 48

# DataForSEO: only fetch for keywords above this opportunity_score threshold
_DATAFORSEO_MIN_SCORE = 50.0

# Big-brand developer substrings (mirrors engine.py — kept local to avoid circular import)
_BIG_BRAND_SUBSTRINGS = frozenset({
    "openai", "google", "meta platforms", "microsoft", "apple inc",
    "amazon.com", "adobe", "netflix", "spotify", "bytedance", "tiktok",
    "snap inc", "linkedin", "pinterest", "samsung", "shopify",
    "salesforce", "zoom video", "slack tech", "dropbox", "airbnb",
    "uber tech", "lyft", "doordash", "duolingo", "match group",
    "epic games", "activision", "electronic arts", "zynga", "king",
    "supercell", "niantic", "sony interactive", "warner bros", "disney",
    "reddit inc", "twitch",
})


# ---------------------------------------------------------------------------
# Scoring formulas
# ---------------------------------------------------------------------------

def _compute_opportunity_score(
    trend_score: float,
    trend_growth: float,
    search_volume: int,
    difficulty: float,
    dominance_score: float,
    apps_count: int,
) -> float:
    """
    Unified opportunity score (0-100):
      trend_pts    (0-30): Google Trends average interest level
      growth_pts   (0-20): Recent trend growth momentum
      volume_pts   (0-25): Search volume (log scale; falls back to apps_count)
      space_pts    (0-25): Open market = low difficulty + low dominance
    """
    trend_pts = min(trend_score / 100.0 * 30.0, 30.0)
    growth_pts = min(max(trend_growth, 0.0) / 100.0 * 20.0, 20.0)

    if search_volume > 0:
        volume_pts = min(log10(search_volume + 1) / log10(100_000) * 25.0, 25.0)
    else:
        # Fallback when no real volume: estimate from apps_count
        volume_pts = min(apps_count / 200.0 * 15.0, 15.0)

    diff_pts = (1.0 - min(difficulty, 100.0) / 100.0) * 12.5
    dom_pts = (1.0 - min(dominance_score, 100.0) / 100.0) * 12.5
    space_pts = diff_pts + dom_pts

    return round(min(trend_pts + growth_pts + volume_pts + space_pts, 100.0), 1)


def _compute_feasibility_score(
    difficulty: float,
    dominance_score: float,
    trend_velocity: float,
    apps_count: int,
) -> float:
    """
    Feasibility score (0-100): how realistic for an indie dev to win?
      diff_pts  (0-35): low difficulty = easier ASO
      dom_pts   (0-35): low dominance = no giant blocking the market
      vel_pts   (0-20): positive trend velocity = rising tide lifts all boats
      scar_pts  (0-10): fewer competing apps = less noise to cut through
    """
    diff_pts = (1.0 - min(difficulty, 100.0) / 100.0) * 35.0
    dom_pts = (1.0 - min(dominance_score, 100.0) / 100.0) * 35.0
    vel_pts = min(max(trend_velocity, 0.0) / 50.0 * 20.0, 20.0)
    scar_pts = max(0.0, (1.0 - min(apps_count, 200) / 200.0) * 10.0)

    return round(min(diff_pts + dom_pts + vel_pts + scar_pts, 100.0), 1)


# ---------------------------------------------------------------------------
# Google Trends Collector
# ---------------------------------------------------------------------------

class GoogleTrendsCollector:
    """
    Collects interest-over-time data from Google Trends via pytrends.
    Uses conservative batching and delays to avoid rate limiting.
    """

    def __init__(self):
        self._pytrends = None  # lazy init

    def _get_pytrends(self):
        if self._pytrends is None:
            try:
                from pytrends.request import TrendReq
                self._pytrends = TrendReq(
                    hl="en-US",
                    tz=360,
                    timeout=(10, 25),
                    retries=2,
                    backoff_factor=0.5,
                )
            except ImportError:
                logger.warning("pytrends not installed — Google Trends disabled. Run: pip install pytrends")
                raise
        return self._pytrends

    def fetch_batch(self, keywords: List[str], timeframe: str = "today 3-m") -> Dict[str, Dict]:
        """
        Fetch trends for up to 5 keywords at once (pytrends limit).
        Returns: {keyword: {trend_score, trend_growth, trend_velocity, weekly_data}}
        Falls back to {} on any error.
        """
        if not settings.google_trends_enabled:
            return {}

        if len(keywords) > 5:
            keywords = keywords[:5]

        try:
            pt = self._get_pytrends()
            pt.build_payload(keywords, cat=0, timeframe=timeframe, geo="US")
            df = pt.interest_over_time()
        except ImportError:
            return {}
        except Exception as e:
            logger.warning(f"Google Trends fetch failed for {keywords}: {e}")
            return {}

        if df is None or df.empty:
            return {}

        results = {}
        for kw in keywords:
            if kw not in df.columns:
                continue
            series = df[kw].dropna()
            if series.empty:
                continue

            values = series.tolist()
            n = len(values)

            # trend_score: average interest over entire period (0-100)
            trend_score = sum(values) / n if n > 0 else 0.0

            # trend_growth: last 4 weeks vs prior 4 weeks
            if n >= 8:
                recent = sum(values[-4:]) / 4
                prior = sum(values[-8:-4]) / 4
                trend_growth = ((recent - prior) / (prior + 1)) * 100.0
            elif n >= 2:
                trend_growth = ((values[-1] - values[0]) / (values[0] + 1)) * 100.0
            else:
                trend_growth = 0.0

            # trend_velocity: last week vs recent 5-week average
            if n >= 5:
                recent_avg = sum(values[-5:]) / 5
                last_val = values[-1]
                trend_velocity = (last_val - recent_avg) / (recent_avg + 1) * 100.0
            else:
                trend_velocity = 0.0

            # weekly sparkline (last 12 data points)
            weekly_data = []
            timestamps = series.index.tolist()
            for ts, val in zip(timestamps[-12:], values[-12:]):
                weekly_data.append({
                    "date": ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts),
                    "interest": int(val),
                })

            results[kw] = {
                "trend_score": round(min(float(trend_score), 100.0), 1),
                "trend_growth": round(float(trend_growth), 1),
                "trend_velocity": round(float(trend_velocity), 1),
                "weekly_data": weekly_data,
            }

        # Polite delay between batches
        time.sleep(2.0)
        return results

    def fetch_related(self, keyword: str) -> List[str]:
        """Get rising related queries for a keyword (for keyword discovery)."""
        if not settings.google_trends_enabled:
            return []
        try:
            pt = self._get_pytrends()
            pt.build_payload([keyword], cat=0, timeframe="today 3-m", geo="US")
            related = pt.related_queries()
            rising = related.get(keyword, {}).get("rising")
            if rising is not None and not rising.empty:
                return rising["query"].tolist()[:10]
        except Exception as e:
            logger.warning(f"Related queries fetch failed for '{keyword}': {e}")
        return []


# ---------------------------------------------------------------------------
# Apple App Store Signals Collector
# ---------------------------------------------------------------------------

class AppleSignalsCollector:
    """
    Derives keyword signals from the iTunes Search API.
    Measures: how many apps rank for a keyword, and how dominant the top app is.
    Free, no credentials needed.
    """

    async def fetch(self, keyword: str, limit: int = 50) -> Dict:
        """
        Search iTunes for `keyword`, return signals:
          {apps_count, dominance_score, top_app_reviews, top_app_rating, top_app_name}
        """
        encoded = urllib.parse.quote_plus(keyword)
        url = (
            f"https://itunes.apple.com/search"
            f"?term={encoded}&media=software&limit={limit}&country=us"
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(url)
                if not r.is_success:
                    return {}
                data = r.json()
        except Exception as e:
            logger.warning(f"Apple signals fetch failed for '{keyword}': {e}")
            return {}

        results = data.get("results", [])
        if not results:
            return {"apps_count": 0, "dominance_score": 0.0}

        apps_count = data.get("resultCount", len(results))
        top = results[0]
        top_reviews = (
            top.get("userRatingCountForCurrentVersion")
            or top.get("userRatingCount", 0)
            or 0
        )
        top_rating = (
            top.get("averageUserRatingForCurrentVersion")
            or top.get("averageUserRating", 0.0)
            or 0.0
        )
        top_name = top.get("trackName", "")
        top_dev = (top.get("artistName") or "").strip().lower()

        # Dominance score from top app review count
        if top_reviews >= 1_000_000:
            dominance_score = 100.0
        elif top_reviews >= 500_000:
            dominance_score = 90.0
        elif top_reviews >= 100_000:
            dominance_score = 75.0
        elif top_reviews >= 50_000:
            dominance_score = 60.0
        elif top_reviews >= 10_000:
            dominance_score = 40.0
        elif top_reviews >= 1_000:
            dominance_score = 20.0
        else:
            dominance_score = 5.0

        # Big-brand developer → extra dominance penalty
        is_big_brand = any(b in top_dev for b in _BIG_BRAND_SUBSTRINGS if len(b) > 5)
        if is_big_brand:
            dominance_score = max(dominance_score, 80.0)

        return {
            "apps_count": apps_count,
            "dominance_score": round(dominance_score, 1),
            "top_app_reviews": top_reviews,
            "top_app_rating": round(float(top_rating), 2),
            "top_app_name": top_name,
        }


# ---------------------------------------------------------------------------
# DataForSEO Collector (optional)
# ---------------------------------------------------------------------------

class DataForSEOCollector:
    """
    Optional integration with DataForSEO for real Google Ads search volume data.
    Only called for high-potential keywords (opportunity_score >= threshold).
    Sign up: https://dataforseo.com (free tier available).
    """

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.base_url = "https://api.dataforseo.com/v3"

    async def fetch_search_volumes(self, keywords: List[str]) -> Dict[str, Dict]:
        """
        Fetch real search volumes for a batch of keywords.
        Returns: {keyword: {search_volume, keyword_difficulty, cpc, competition}}
        """
        if not self.username or not self.password:
            return {}

        payload = [{
            "keywords": keywords,
            "location_name": "United States",
            "language_name": "English",
        }]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{self.base_url}/keywords_data/google_ads/search_volume/live",
                    json=payload,
                    auth=(self.username, self.password),
                )
                if not r.is_success:
                    logger.warning(f"DataForSEO returned HTTP {r.status_code}")
                    return {}
                data = r.json()
        except Exception as e:
            logger.warning(f"DataForSEO fetch failed: {e}")
            return {}

        results: Dict[str, Dict] = {}
        try:
            for task in data.get("tasks", []):
                for item in (task.get("result") or []):
                    kw = (item.get("keyword") or "").lower().strip()
                    if not kw:
                        continue
                    results[kw] = {
                        "search_volume": item.get("search_volume") or 0,
                        "keyword_difficulty": item.get("keyword_difficulty") or 0,
                        "cpc": item.get("cpc") or 0.0,
                        "competition": (item.get("competition_index") or 0.0) * 100.0,
                    }
        except Exception as e:
            logger.warning(f"DataForSEO parse error: {e}")

        return results


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

class KeywordIntelligencePipeline:
    """
    Orchestrates multi-layer keyword enrichment.

    Phases:
      1. discover_keywords()        — add seed + trending keywords to DB
      2. enrich_with_trends()       — Google Trends (batched sync, rate-limited)
      3. enrich_with_apple_signals()— iTunes Search API (async, concurrent)
      4. enrich_with_dataforseo()   — DataForSEO (optional, cost-controlled)
      5. recompute_scores()         — recompute opportunity_score + feasibility_score

    Each phase is independently failsafe — errors are logged and the next
    phase continues. run_full_pipeline() returns a summary dict.
    """

    def __init__(self, db: Session):
        self.db = db
        self.trends_collector = GoogleTrendsCollector()
        self.apple_collector = AppleSignalsCollector()
        self.dataforseo_collector: Optional[DataForSEOCollector] = None
        if settings.dataforseo_enabled and settings.dataforseo_username:
            self.dataforseo_collector = DataForSEOCollector(
                settings.dataforseo_username,
                settings.dataforseo_password,
            )

    # ------------------------------------------------------------------
    # Phase 1: Keyword discovery
    # ------------------------------------------------------------------

    async def discover_keywords(self) -> int:
        """
        Add seed keywords and Google Trends related queries to the DB.
        Returns count of newly added keywords.
        """
        new_count = 0

        # 1a. Add all seed keywords not yet in DB
        for term in _SEED_KEYWORDS:
            existing = self.db.query(Keyword).filter(Keyword.term == term).first()
            if not existing:
                kw = Keyword(term=term, search_volume=0, difficulty=30.0, trend=3.0)
                self.db.add(kw)
                new_count += 1

        if new_count > 0:
            self.db.commit()
            logger.info(f"Keyword discovery: added {new_count} seed keywords")

        # 1b. Discover related keywords from Google Trends (one seed per category)
        related_new = 0
        if settings.google_trends_enabled:
            for category, seeds in _CATEGORY_SEEDS.items():
                if not seeds:
                    continue
                try:
                    related = self.trends_collector.fetch_related(seeds[0])
                    for raw_term in related:
                        term = raw_term.lower().strip()
                        if len(term) < 3 or len(term) > 80:
                            continue
                        existing = self.db.query(Keyword).filter(Keyword.term == term).first()
                        if not existing:
                            kw = Keyword(term=term, search_volume=0, difficulty=40.0, trend=5.0)
                            self.db.add(kw)
                            related_new += 1
                    time.sleep(2.0)  # polite delay
                except Exception as e:
                    logger.warning(f"Related keyword discovery failed for '{seeds[0]}': {e}")

            if related_new > 0:
                self.db.commit()
                logger.info(f"Keyword discovery: added {related_new} related keywords via Google Trends")

        return new_count + related_new

    # ------------------------------------------------------------------
    # Phase 2: Google Trends enrichment
    # ------------------------------------------------------------------

    def enrich_with_trends(self, keywords: List[Keyword]) -> int:
        """
        Batch-fetch Google Trends data for stale keywords.
        Skips keywords updated within TRENDS_TTL_HOURS.
        Returns count of keywords updated.
        """
        if not settings.google_trends_enabled:
            logger.info("Google Trends disabled — skipping trends enrichment")
            return 0

        cutoff = datetime.utcnow() - timedelta(hours=_TRENDS_TTL_HOURS)
        stale = [
            kw for kw in keywords
            if not kw.last_enriched
            or kw.last_enriched.replace(tzinfo=None) < cutoff
        ]

        if not stale:
            logger.info("All keywords have fresh trend data — skipping")
            return 0

        logger.info(f"Enriching {len(stale)} keywords with Google Trends (batches of 5)")
        updated = 0

        for i in range(0, len(stale), 5):
            batch = stale[i:i + 5]
            terms = [kw.term for kw in batch]
            try:
                trend_data = self.trends_collector.fetch_batch(terms)
                for kw in batch:
                    data = trend_data.get(kw.term, {})
                    if data:
                        kw.trend_score = data["trend_score"]
                        kw.trend_growth = data["trend_growth"]
                        kw.trend_velocity = data["trend_velocity"]
                        kw.last_enriched = datetime.utcnow()
                        self._save_trend_points(kw.id, data.get("weekly_data", []))
                        updated += 1
                self.db.commit()
            except Exception as e:
                logger.warning(f"Trends batch {terms} failed: {e}")
                try:
                    self.db.rollback()
                except Exception:
                    pass
                time.sleep(5.0)

        logger.info(f"Google Trends enrichment: {updated}/{len(stale)} keywords updated")
        return updated

    def _save_trend_points(self, keyword_id: int, weekly_data: List[Dict]):
        """Upsert weekly trend data points into keyword_trends table."""
        for point in weekly_data:
            date_str = point.get("date")
            interest = point.get("interest", 0)
            if not date_str:
                continue
            try:
                week_start = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            try:
                stmt = (
                    pg_insert(KeywordTrend)
                    .values(
                        keyword_id=keyword_id,
                        week_start=week_start,
                        interest_score=interest,
                    )
                    .on_conflict_do_update(
                        index_elements=["keyword_id", "week_start"],
                        set_={"interest_score": interest, "captured_at": func.now()},
                    )
                )
                self.db.execute(stmt)
            except Exception as e:
                logger.warning(f"Trend point save failed (kw_id={keyword_id}, date={date_str}): {e}")

    # ------------------------------------------------------------------
    # Phase 3: Apple App Store signal enrichment
    # ------------------------------------------------------------------

    async def enrich_with_apple_signals(self, keywords: List[Keyword]) -> int:
        """
        Fetch iTunes search signals for each keyword concurrently (chunks of 10).
        Returns count of keywords updated.
        """
        updated = 0

        for i in range(0, len(keywords), 10):
            batch = keywords[i:i + 10]
            tasks = [self.apple_collector.fetch(kw.term) for kw in batch]
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for kw, result in zip(batch, results):
                    if isinstance(result, Exception):
                        logger.warning(f"Apple signals failed for '{kw.term}': {result}")
                        continue
                    if not result:
                        continue
                    kw.dominance_score = result.get("dominance_score", 0.0)
                    # Use max of stored vs fresh apps_count
                    kw.apps_count = max(kw.apps_count or 0, result.get("apps_count", 0))
                    updated += 1
                self.db.commit()
            except Exception as e:
                logger.warning(f"Apple signals batch failed: {e}")
                try:
                    self.db.rollback()
                except Exception:
                    pass
            await asyncio.sleep(0.5)

        logger.info(f"Apple signals enrichment: {updated}/{len(keywords)} keywords updated")
        return updated

    # ------------------------------------------------------------------
    # Phase 4: DataForSEO enrichment (optional)
    # ------------------------------------------------------------------

    async def enrich_with_dataforseo(self, keywords: List[Keyword]) -> int:
        """
        Fetch real search volume data for high-opportunity keywords.
        Only runs when dataforseo_enabled=True and credentials are configured.
        Returns count of keywords updated.
        """
        if not self.dataforseo_collector:
            return 0

        eligible = [
            kw for kw in keywords
            if (kw.opportunity_score or 0) >= _DATAFORSEO_MIN_SCORE
        ]

        if not eligible:
            logger.info("No keywords meet DataForSEO threshold — skipping")
            return 0

        logger.info(f"DataForSEO enrichment: {len(eligible)} eligible keywords")
        updated = 0

        for i in range(0, len(eligible), 50):
            batch = eligible[i:i + 50]
            terms = [kw.term for kw in batch]
            try:
                seo_data = await self.dataforseo_collector.fetch_search_volumes(terms)
                for kw in batch:
                    data = seo_data.get(kw.term, {})
                    if not data:
                        continue
                    if data.get("search_volume"):
                        kw.search_volume = int(data["search_volume"])
                    if data.get("keyword_difficulty"):
                        kw.difficulty = float(data["keyword_difficulty"])
                    kw.cpc = float(data.get("cpc", 0.0))
                    kw.competition_score = float(data.get("competition", 0.0))
                    updated += 1
                self.db.commit()
            except Exception as e:
                logger.warning(f"DataForSEO batch failed: {e}")
                try:
                    self.db.rollback()
                except Exception:
                    pass

        logger.info(f"DataForSEO enrichment: {updated} keywords updated")
        return updated

    # ------------------------------------------------------------------
    # Phase 5: Unified scoring
    # ------------------------------------------------------------------

    def recompute_scores(self, keywords: List[Keyword]) -> int:
        """
        Recompute opportunity_score and feasibility_score for all keywords
        using whatever signals are available (graceful fallback).
        Returns count of keywords scored.
        """
        updated = 0
        for kw in keywords:
            try:
                opp = _compute_opportunity_score(
                    trend_score=kw.trend_score or 0.0,
                    trend_growth=kw.trend_growth or 0.0,
                    search_volume=kw.search_volume or 0,
                    difficulty=kw.difficulty or 30.0,
                    dominance_score=kw.dominance_score or 0.0,
                    apps_count=kw.apps_count or 0,
                )
                feas = _compute_feasibility_score(
                    difficulty=kw.difficulty or 30.0,
                    dominance_score=kw.dominance_score or 0.0,
                    trend_velocity=kw.trend_velocity or 0.0,
                    apps_count=kw.apps_count or 0,
                )
                kw.opportunity_score = opp
                kw.feasibility_score = feas
                updated += 1
            except Exception as e:
                logger.warning(f"Score recompute failed for '{kw.term}': {e}")

        self.db.commit()
        logger.info(f"Keyword scoring: {updated} keywords scored")
        return updated

    # ------------------------------------------------------------------
    # Main entry points
    # ------------------------------------------------------------------

    async def run_full_pipeline(self, max_keywords: int = 500) -> Dict:
        """
        Run all pipeline phases sequentially.
        Each phase is wrapped in try/except so a failing phase
        does not block subsequent phases.
        Returns summary dict.
        """
        summary = {
            "discovered": 0,
            "trends_updated": 0,
            "apple_updated": 0,
            "seo_updated": 0,
            "scored": 0,
        }

        # Phase 1: Discover new keywords
        try:
            summary["discovered"] = await self.discover_keywords()
        except Exception as e:
            logger.error(f"Keyword discovery failed: {e}")

        # Fetch all keywords up to max_keywords
        keywords = self.db.query(Keyword).limit(max_keywords).all()

        # Phase 2: Google Trends
        try:
            summary["trends_updated"] = self.enrich_with_trends(keywords)
        except Exception as e:
            logger.error(f"Google Trends enrichment failed: {e}")

        # Phase 3: Apple App Store signals
        try:
            summary["apple_updated"] = await self.enrich_with_apple_signals(keywords)
        except Exception as e:
            logger.error(f"Apple signals enrichment failed: {e}")

        # Refresh keywords from DB before scoring (captures Apple signal updates)
        keywords = self.db.query(Keyword).limit(max_keywords).all()

        # Phase 4: DataForSEO (optional)
        try:
            summary["seo_updated"] = await self.enrich_with_dataforseo(keywords)
        except Exception as e:
            logger.error(f"DataForSEO enrichment failed: {e}")

        # Refresh again for scoring
        keywords = self.db.query(Keyword).limit(max_keywords).all()

        # Phase 5: Recompute scores
        try:
            summary["scored"] = self.recompute_scores(keywords)
        except Exception as e:
            logger.error(f"Score recompute failed: {e}")

        logger.info(f"Keyword intelligence pipeline complete: {summary}")
        return summary

    async def run_trends_only(self, max_keywords: int = 200) -> int:
        """Quick job: only refresh Google Trends data (no Apple/SEO calls)."""
        keywords = self.db.query(Keyword).limit(max_keywords).all()
        return self.enrich_with_trends(keywords)

    async def run_apple_signals_only(self, max_keywords: int = 300) -> int:
        """Quick job: only refresh Apple App Store signals."""
        keywords = self.db.query(Keyword).limit(max_keywords).all()
        return await self.enrich_with_apple_signals(keywords)

    async def run_scoring_only(self) -> int:
        """Quick job: only recompute scores (no external API calls)."""
        keywords = self.db.query(Keyword).all()
        return self.recompute_scores(keywords)

    def get_trending_keywords(self, limit: int = 20) -> List[Keyword]:
        """
        Return the top trending keywords by Google Trends velocity + score.
        Used by Niche Radar and Opportunities pages.
        """
        return (
            self.db.query(Keyword)
            .filter(
                Keyword.trend_score > 0,
                Keyword.opportunity_score > 0,
            )
            .order_by(
                (Keyword.trend_velocity + Keyword.trend_growth / 2).desc(),
                Keyword.opportunity_score.desc(),
            )
            .limit(limit)
            .all()
        )

    def get_keyword_trend_points(self, keyword_id: int, weeks: int = 12) -> List[KeywordTrend]:
        """Return weekly trend data points for a keyword (for sparkline charts)."""
        cutoff = datetime.utcnow() - timedelta(weeks=weeks)
        return (
            self.db.query(KeywordTrend)
            .filter(
                KeywordTrend.keyword_id == keyword_id,
                KeywordTrend.week_start >= cutoff,
            )
            .order_by(KeywordTrend.week_start.asc())
            .all()
        )
