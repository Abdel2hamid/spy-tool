"""
App Store Query Parser
======================
Detects whether a search query is a direct App Store URL, a raw Apple trackId,
or a plain text keyword search.

Usage:
    from app.utils.parse_appstore_query import parse_appstore_query

    result = parse_appstore_query("https://apps.apple.com/us/app/fantastical/id718043190")
    # → ParsedQuery(type='url', track_id='718043190')

    result = parse_appstore_query("718043190")
    # → ParsedQuery(type='track_id', track_id='718043190')

    result = parse_appstore_query("focus timer productivity")
    # → ParsedQuery(type='text', track_id=None)
"""

import re
from dataclasses import dataclass
from typing import Literal, Optional

# App Store URL: https://apps.apple.com/{country}/app/{name}/id{trackId}
# Also matches bare domain without scheme, e.g. "apps.apple.com/..."
_APPLE_STORE_RE = re.compile(
    r"apps\.apple\.com/[^/\s]+/app(?:/[^/\s?#]*)?/id(\d{6,13})",
    re.IGNORECASE,
)

# iTunes URL: https://itunes.apple.com/{country}/app/{name}/id{trackId}
_ITUNES_RE = re.compile(
    r"itunes\.apple\.com/[^/\s]+/app(?:/[^/\s?#]*)?/id(\d{6,13})",
    re.IGNORECASE,
)

# Bare /id{trackId} slug — e.g. "id718043190"
_ID_SLUG_RE = re.compile(r"^id(\d{6,13})$", re.IGNORECASE)

# Plain numeric Apple trackId (6–13 digits).
# Apple trackIds are typically 9–10 digits, but can be as short as 6 and we
# allow up to 13 for future-proofing.
_NUMERIC_ID_RE = re.compile(r"^(\d{6,13})$")


@dataclass
class ParsedQuery:
    """Result of parsing an app search query."""
    type: Literal["url", "track_id", "text"]
    track_id: Optional[str] = None


def parse_appstore_query(query: str) -> ParsedQuery:
    """
    Detect the type of an app search query.

    Returns a ParsedQuery with:
    - type='url'      — query contains an App Store or iTunes URL → track_id is extracted
    - type='track_id' — query is a numeric Apple ID or 'id{digits}' slug → track_id is extracted
    - type='text'     — everything else → normal keyword search; track_id is None
    """
    if not query:
        return ParsedQuery(type="text")

    q = query.strip()

    # Check URL patterns first (URLs contain dots/slashes so they won't match numeric-only)
    for pattern in (_APPLE_STORE_RE, _ITUNES_RE):
        m = pattern.search(q)
        if m:
            return ParsedQuery(type="url", track_id=m.group(1))

    # id-slug: "id718043190"
    m = _ID_SLUG_RE.match(q)
    if m:
        return ParsedQuery(type="track_id", track_id=m.group(1))

    # Plain numeric ID
    m = _NUMERIC_ID_RE.match(q)
    if m:
        return ParsedQuery(type="track_id", track_id=m.group(1))

    return ParsedQuery(type="text")
