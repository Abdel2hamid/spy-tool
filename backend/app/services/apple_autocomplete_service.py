"""
Apple Autocomplete Service
==========================
Fetches App Store search suggestions from Apple's MZSearchHints endpoint.

Usage::
    from app.services.apple_autocomplete_service import fetch_autocomplete
    suggestions = fetch_autocomplete("youtube")
    # ["youtube music", "youtube movies", "youtube music app", ...]
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import List

logger = logging.getLogger(__name__)

_HINTS_URL = (
    "https://search.itunes.apple.com/WebObjects/MZSearchHints.woa/wa/hints"
)
_TIMEOUT = 10
_USER_AGENT = "AppStoreSpy/1.0"


def fetch_autocomplete(keyword: str, country: str = "us") -> List[str]:
    """
    Fetch Apple App Store autocomplete suggestions for *keyword*.

    Returns up to 20 unique suggestions, each at least 3 characters long,
    in the order Apple returns them.

    Returns an empty list on any network or parse error (never raises).
    """
    if not keyword or len(keyword.strip()) < 2:
        return []

    params = urllib.parse.urlencode({
        "term": keyword.strip(),
        "media": "software",
        "country": country,
    })
    url = f"{_HINTS_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        logger.debug(f"[Autocomplete] fetch failed for {keyword!r}: {exc}")
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
