"""
apple_http_client.py
====================
Centralised HTTP client for all Apple iTunes / App Store API requests.

Features:
  - Realistic Safari User-Agent and headers
  - Retry with exponential backoff (distinguishes 403/429/500)
  - Per-request timeout (default 15s)
  - JSON response parsing with validation
  - Circuit-breaker: stops hammering Apple after repeated 403s

Usage:
    from app.services.apple_http_client import apple_fetch, apple_fetch_json

    data = apple_fetch_json("https://itunes.apple.com/search", params={"term": "fitness"})
"""

import json
import logging
import random
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared headers — realistic Safari on macOS
# ---------------------------------------------------------------------------
APPLE_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}

# ---------------------------------------------------------------------------
# Circuit-breaker state (module-level, resets on process restart)
# ---------------------------------------------------------------------------
_consecutive_403s = 0
_CIRCUIT_BREAKER_THRESHOLD = 5  # trip after 5 consecutive 403s
_circuit_open_until = 0.0  # timestamp when circuit re-closes
_breaker_lock = threading.Lock()  # state is mutated from threadpool + worker threads


def _is_circuit_open() -> bool:
    with _breaker_lock:
        return (
            _consecutive_403s >= _CIRCUIT_BREAKER_THRESHOLD
            and time.monotonic() < _circuit_open_until
        )


def _record_success():
    global _consecutive_403s
    with _breaker_lock:
        _consecutive_403s = 0


def _record_403():
    global _consecutive_403s, _circuit_open_until
    with _breaker_lock:
        _consecutive_403s += 1
        tripped = _consecutive_403s >= _CIRCUIT_BREAKER_THRESHOLD
        if tripped:
            _circuit_open_until = time.monotonic() + 120  # back off 2 minutes
    if tripped:
        logger.warning(
            "[AppleHTTP] Circuit breaker OPEN — %d consecutive 403s. "
            "Pausing Apple requests for 120s.",
            _CIRCUIT_BREAKER_THRESHOLD,
        )


# ---------------------------------------------------------------------------
# Core fetch
# ---------------------------------------------------------------------------

def apple_fetch(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
    max_retries: int = 2,
    headers: Optional[Dict[str, str]] = None,
) -> Optional[bytes]:
    """
    Fetch raw bytes from an Apple API endpoint.

    - Appends `params` as URL query string (safely encoded).
    - Retries on 429/500/503 with exponential backoff.
    - Returns None on 403 (after recording circuit-breaker hit).
    - Returns None on permanent failure after retries exhausted.
    """
    if _is_circuit_open():
        logger.debug("[AppleHTTP] Circuit open — skipping request to %s", url)
        return None

    if params:
        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        full_url = f"{url}?{qs}"
    else:
        full_url = url

    merged_headers = {**APPLE_HEADERS, **(headers or {})}
    req = urllib.request.Request(full_url, headers=merged_headers)

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 2):  # attempt 1..max_retries+1
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                _record_success()
                return body

        except urllib.error.HTTPError as e:
            status = e.code
            if status == 403:
                _record_403()
                logger.warning(
                    "[AppleHTTP] 403 Forbidden on %s (attempt %d)",
                    url, attempt,
                )
                return None  # don't retry 403 — Apple is blocking us

            if status == 429:
                # Retry-After may be seconds or an HTTP-date — never let it raise
                try:
                    retry_after = int(e.headers.get("Retry-After", ""))
                except (ValueError, TypeError):
                    retry_after = 2 ** attempt
                logger.warning(
                    "[AppleHTTP] 429 Rate-limited on %s — sleeping %ds",
                    url, retry_after,
                )
                time.sleep(min(retry_after, 30))
                last_exc = e
                continue

            if status >= 500:
                delay = 2 ** attempt + random.uniform(0, 0.5)
                logger.warning(
                    "[AppleHTTP] %d on %s — retrying in %ds (attempt %d/%d)",
                    status, url, delay, attempt, max_retries + 1,
                )
                time.sleep(delay)
                last_exc = e
                continue

            # Other 4xx — don't retry
            logger.warning("[AppleHTTP] %d on %s — not retrying", status, url)
            return None

        except (TimeoutError, socket.timeout) as e:
            logger.warning(
                "[AppleHTTP] Timeout on %s (attempt %d/%d)",
                url, attempt, max_retries + 1,
            )
            last_exc = e
            if attempt <= max_retries:
                time.sleep(1)
            continue

        except urllib.error.URLError as e:
            if isinstance(e.reason, (TimeoutError, socket.timeout)):
                logger.warning(
                    "[AppleHTTP] URLError/timeout on %s (attempt %d/%d)",
                    url, attempt, max_retries + 1,
                )
                last_exc = e
                if attempt <= max_retries:
                    time.sleep(1)
                continue
            logger.warning("[AppleHTTP] URLError on %s: %s", url, e)
            return None

        except Exception as e:
            logger.warning("[AppleHTTP] Unexpected error on %s: %s", url, e)
            last_exc = e
            if attempt <= max_retries:
                time.sleep(1)
            continue

    logger.warning(
        "[AppleHTTP] All %d attempts exhausted for %s (last: %s)",
        max_retries + 1, url, last_exc,
    )
    return None


def apple_fetch_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
    max_retries: int = 2,
    headers: Optional[Dict[str, str]] = None,
) -> Optional[Dict]:
    """
    Fetch and parse JSON from an Apple API endpoint.
    Returns the parsed dict, or None on failure.
    """
    body = apple_fetch(
        url,
        params=params,
        timeout=timeout,
        max_retries=max_retries,
        headers=headers,
    )
    if body is None:
        return None
    try:
        return json.loads(body)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("[AppleHTTP] JSON parse error from %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Convenience constants for common Apple endpoints
# ---------------------------------------------------------------------------
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
ITUNES_HINTS_URL = "https://search.itunes.apple.com/WebObjects/MZSearchHints.woa/wa/hints"
