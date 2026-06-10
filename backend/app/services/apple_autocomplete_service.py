"""
Apple Autocomplete Service
==========================
Fetches App Store search suggestions from Apple's MZSearchHints endpoint.

Usage::
    from app.services.apple_autocomplete_service import fetch_autocomplete
    suggestions = fetch_autocomplete("youtube")
    # ["youtube music", "youtube movies", "youtube music app", ...]
"""

import logging
from typing import List

from app.services.apple_http_client import apple_fetch_json, ITUNES_HINTS_URL

logger = logging.getLogger(__name__)

_TIMEOUT = 10


def fetch_autocomplete(keyword: str, country: str = "us") -> List[str]:
    """
    Fetch Apple App Store autocomplete suggestions for *keyword*.

    Returns up to 20 unique suggestions, each at least 3 characters long,
    in the order Apple returns them.

    Returns an empty list on any network or parse error (never raises).
    """
    if not keyword or len(keyword.strip()) < 2:
        return []

    data = apple_fetch_json(
        ITUNES_HINTS_URL,
        params={
            "term": keyword.strip(),
            "media": "software",
            "country": country,
        },
        timeout=_TIMEOUT,
    )
    if not data:
        return []

    # Apple returns {"hints": [{"term": "youtube music"}, ...]}
    hints = data.get("hints", [])
    seen: set = set()
    results: List[str] = []

    for h in hints:
        term = (h.get("term") or "").strip().lower()
        if len(term) >= 3 and term not in seen:
            seen.add(term)
            results.append(term)
            if len(results) >= 20:
                break

    return results
