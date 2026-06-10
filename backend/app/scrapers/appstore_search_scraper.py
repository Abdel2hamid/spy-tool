"""
App Store Search Scraper
========================
Uses the iTunes Search API to fetch App Store search results.

Previously Playwright-based; replaced with iTunes API to avoid requiring
browser binaries (which are unavailable on Railway and similar PaaS platforms).

Trade-offs vs the Playwright implementation:
  ✅ No browser needed — works on any server
  ✅ ~10× faster per query (~300 ms vs 5-10 s)
  ✅ No CSS selectors to break when Apple redesigns the page
  ❌ No sponsored/Apple Search Ads detection (all results treated as organic)
  ❌ Result order may differ slightly from the visual storefront

Public interface is unchanged — callers are unaffected.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List

from app.services.apple_http_client import apple_fetch_json, ITUNES_SEARCH_URL, ITUNES_LOOKUP_URL

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 12  # seconds for apple_fetch_json calls


class AppStoreSearchScraper:
    """
    iTunes Search API-based App Store search result scraper.

    Usage (async context manager — same interface as the old Playwright version):
        async with AppStoreSearchScraper() as scraper:
            result = await scraper.search("productivity", country="us")

    Can also be used without the context manager:
        scraper = AppStoreSearchScraper()
        result = await scraper.search("productivity")
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 30_000):
        # headless and timeout_ms kept for API compatibility; ignored.
        self._timeout = max(timeout_ms // 1000, _DEFAULT_TIMEOUT)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def close(self):
        """No-op — kept for API compatibility."""
        pass

    # ------------------------------------------------------------------
    # Public API (same signatures as the old Playwright scraper)
    # ------------------------------------------------------------------

    async def search(
        self,
        keyword: str,
        country: str = "us",
        max_results: int = 20,
        retries: int = 2,
    ) -> Dict:
        """
        Fetch App Store search results for *keyword* in *country* via iTunes API.

        Returns::

            {
                "keyword": "ai photo",
                "country": "us",
                "captured_at": "2024-...",
                "results": [
                    {
                        "position": 1,
                        "organic_position": 1,
                        "app_id": "123456",
                        "app_name": "...",
                        "developer": "...",
                        "icon": "https://...",
                        "is_sponsored": False,   # always False — iTunes API has no ad data
                    },
                    ...
                ]
            }
        """
        # Retries are handled by apple_fetch_json internally
        try:
            return await asyncio.to_thread(
                self._search_sync, keyword, country, max_results
            )
        except Exception as exc:
            logger.error(
                f"[search] failed for {keyword!r}: {exc}"
            )
            return self._empty_result(keyword, country)

    async def search_many(
        self,
        keywords: List[str],
        country: str = "us",
        max_results: int = 20,
        concurrency: int = 10,
    ) -> List[Dict]:
        """
        Search multiple keywords with bounded concurrency.
        Returns a list of result dicts (one per keyword, in input order).
        """
        sem = asyncio.Semaphore(concurrency)

        async def _bounded(kw: str) -> Dict:
            async with sem:
                result = await self.search(kw, country, max_results)
                await asyncio.sleep(0.3)  # polite delay
                return result

        return await asyncio.gather(*[_bounded(kw) for kw in keywords])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search_sync(self, keyword: str, country: str, max_results: int) -> Dict:
        """Blocking iTunes Search API call — run inside asyncio.to_thread()."""
        logger.info(f"[search] {keyword!r} / {country}")

        data = apple_fetch_json(
            ITUNES_SEARCH_URL,
            params={
                "term": keyword.strip(),
                "country": country.lower(),
                "entity": "software",
                "limit": min(max_results, 200),
                "lang": "en_us",
            },
            timeout=self._timeout,
        )
        if not data:
            return self._empty_result(keyword, country)

        items = data.get("results", [])
        results = []
        for i, item in enumerate(items[:max_results]):
            results.append({
                "position": i + 1,
                "organic_position": i + 1,          # all organic — no sponsored via API
                "app_id": str(item.get("trackId", "")),
                "app_name": item.get("trackName", ""),
                "developer": item.get("artistName", ""),
                "icon": item.get("artworkUrl100", ""),
                "is_sponsored": False,               # iTunes API has no ad placement data
            })

        logger.info(f"[search] {keyword!r}: {len(results)} results (iTunes API)")
        return {
            "keyword": keyword,
            "country": country,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
        }

    @staticmethod
    def _fetch_icons(app_ids: List[str], country: str = "us") -> Dict[str, str]:
        """
        Batch-fetch artworkUrl100 from iTunes Lookup API.
        Returns a dict mapping app_id → icon_url.
        (Kept for API compatibility; search() already includes icons from iTunes.)
        """
        if not app_ids:
            return {}
        try:
            ids_param = ",".join(app_ids[:50])
            data = apple_fetch_json(
                ITUNES_LOOKUP_URL,
                params={"id": ids_param, "country": country, "entity": "software"},
                timeout=_DEFAULT_TIMEOUT,
            )
            if not data:
                return {}
            return {
                str(item["trackId"]): item.get("artworkUrl100", "")
                for item in data.get("results", [])
                if "trackId" in item
            }
        except Exception as exc:
            logger.debug(f"Icon batch lookup failed: {exc}")
            return {}

    @staticmethod
    def _empty_result(keyword: str, country: str) -> Dict:
        return {
            "keyword": keyword,
            "country": country,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "results": [],
        }


# ---------------------------------------------------------------------------
# Standalone test entry-point
# ---------------------------------------------------------------------------

async def _test():
    logging.basicConfig(level=logging.INFO)
    async with AppStoreSearchScraper() as scraper:
        result = await scraper.search("productivity", country="us", max_results=20)
        print(f"\nKeyword: {result['keyword']} ({result['country']})")
        print(f"Results: {len(result['results'])}")
        for r in result["results"]:
            print(f"  #{r['position']:>2}  {r['app_id']:<12}  {r['app_name'][:40]}")


if __name__ == "__main__":
    asyncio.run(_test())
