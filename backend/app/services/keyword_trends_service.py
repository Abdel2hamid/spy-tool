"""
Keyword Trends Service
======================
Fetches Google Trends interest data for a keyword and computes a trend score
and direction using the last 12 months of data.

Note: Google Trends blocks most cloud/datacenter IPs.  The fetch always
returns gracefully — callers receive ``{"trend_score": 0, "trend_direction":
"stable"}`` when the request fails so the rest of the pipeline continues.

Usage::
    from app.services.keyword_trends_service import fetch_trend_score
    result = fetch_trend_score("youtube music")
    # {"trend_score": 78, "trend_direction": "rising"}
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


def fetch_trend_score(keyword: str, country: str = "US") -> Dict:
    """
    Return Google Trends data for *keyword* over the last 12 months.

    Output::

        {
            "trend_score":     int,   # 0-100, average interest last 12 months
            "trend_direction": str,   # "rising" | "stable" | "declining"
        }

    Direction rules:
      • last-3-month avg > prev-3-month avg  → "rising"
      • last-3-month avg < prev-3-month avg  → "declining"
      • within ±5 pts                        → "stable"
    """
    _default = {"trend_score": 0, "trend_direction": "stable"}

    if not keyword or not keyword.strip():
        return _default

    try:
        from pytrends.request import TrendReq

        pt = TrendReq(hl="en-US", tz=0, timeout=(5, 15), retries=1, backoff_factor=0.5)
        pt.build_payload([keyword], cat=0, timeframe="today 12-m", geo=country)
        df = pt.interest_over_time()

        if df is None or df.empty or keyword not in df.columns:
            return _default

        series = df[keyword].dropna().tolist()
        if not series:
            return _default

        trend_score = int(round(sum(series) / len(series)))

        # Direction: compare last 3 months vs previous 3 months
        if len(series) >= 6:
            last3 = sum(series[-3:]) / 3
            prev3 = sum(series[-6:-3]) / 3
            if last3 > prev3 + 5:
                direction = "rising"
            elif last3 < prev3 - 5:
                direction = "declining"
            else:
                direction = "stable"
        else:
            direction = "stable"

        return {"trend_score": max(0, min(trend_score, 100)), "trend_direction": direction}

    except Exception as exc:
        logger.debug(f"[Trends] fetch failed for {keyword!r}: {exc}")
        return _default
