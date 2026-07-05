import asyncio
import json
from typing import Any, List, Dict, Optional
import logging

from app.services.apple_http_client import apple_fetch_json, ITUNES_SEARCH_URL

# Playwright is an optional dev dependency — only needed for keyword rank tracking.
# The core scraping paths (iTunes API, RSS feeds) work without it.
try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None  # type: ignore[assignment]
    _PLAYWRIGHT_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# iTunes RSS feed chart identifiers (old JSON format — still works)
_CHART_SLUG = {
    "topfree": "topfreeapplications",
    "toppaid": "toppaidapplications",
    "topgrossing": "topgrossingapplications",
}

# Apple App Store genre IDs — keyed by normalised slug
_GENRE_IDS: Dict[str, str] = {
    "productivity": "6007",
    "utilities": "6002",
    "finance": "6015",
    "games": "6014",
    "health-fitness": "6013",
    "education": "6017",
    "entertainment": "6016",
    "social-networking": "6005",
    "music": "6011",
    "photo-video": "6008",
    "travel": "6003",
    "news": "6009",
    "sports": "6004",
    "lifestyle": "6012",
    "business": "6000",
    "medical": "6020",
    "food-drink": "6023",
    "reference": "6006",
    "navigation": "6010",
    "weather": "6001",
    "books": "6018",
}


def _category_to_genre_id(category: Optional[str]) -> str:
    """Convert a category name/slug to an Apple genre ID. Returns 'all' if unknown."""
    if not category:
        return "all"
    slug = category.lower().replace(" & ", "-").replace(" ", "-")
    return _GENRE_IDS.get(slug, "all")


class AppStoreScraper:
    def __init__(self):
        self.browser: Optional[Any] = None
        self.page: Optional[Any] = None
        self.base_url = "https://apps.apple.com"

    async def init(self):
        if not _PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not installed — AppStoreScraper.init() skipped")
            return
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(headless=True)
        self.page = await self.browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        )

    async def close(self):
        if self.browser:
            await self.browser.close()

    def _search_sync(self, keyword: str, limit: int) -> List[Dict]:
        """Blocking iTunes Search API call — always call via asyncio.to_thread."""
        results = []
        try:
            data = apple_fetch_json(
                ITUNES_SEARCH_URL,
                params={"term": keyword, "entity": "software", "limit": limit, "country": "us"},
                timeout=15,
            )
            if not data:
                return results

            for i, app in enumerate(data.get("results", [])):
                track_id = app.get("trackId")
                if not track_id:
                    continue
                results.append({
                    "app_id": str(track_id),
                    "name": app.get("trackName"),
                    "developer": app.get("sellerName") or app.get("artistName"),
                    "icon_url": app.get("artworkUrl100"),
                    "rating": app.get("averageUserRating"),
                    "rank": i + 1,
                    "keyword": keyword,
                })
        except Exception as e:
            logger.error(f"Error searching for '{keyword}': {e}")
        return results

    async def get_search_results(self, keyword: str, limit: int = 200) -> List[Dict]:
        return await asyncio.to_thread(self._search_sync, keyword, limit)

    def _get_top_charts_sync(self, chart_type: str, genre_id: str, limit: int, country: str = "us") -> List[Dict]:
        """
        Fetch top charts via the iTunes RSS feed (JSON format, no Playwright required).

        URL pattern (per storefront):
          https://itunes.apple.com/{cc}/rss/{chart}/limit={limit}/genre={genreId}/json
          https://itunes.apple.com/{cc}/rss/{chart}/limit={limit}/json   (all genres)
        """
        cc = (country or "us").lower()
        chart_slug = _CHART_SLUG.get(chart_type, "topfreeapplications")
        if genre_id and genre_id != "all":
            url = (
                f"https://itunes.apple.com/{cc}/rss/{chart_slug}"
                f"/limit={limit}/genre={genre_id}/json"
            )
        else:
            url = f"https://itunes.apple.com/{cc}/rss/{chart_slug}/limit={limit}/json"

        results = []
        try:
            data = apple_fetch_json(url, timeout=20)
            if not data:
                return results

            entries = data.get("feed", {}).get("entry", [])
            for i, entry in enumerate(entries):
                app_id = entry.get("id", {}).get("attributes", {}).get("im:id")
                if not app_id:
                    continue

                cat_attrs = entry.get("category", {}).get("attributes", {})
                category_name = cat_attrs.get("label")
                genre_id_val = cat_attrs.get("im:id")

                images = entry.get("im:image", [])
                icon_url = images[-1].get("label") if images else None

                results.append({
                    "app_id": str(app_id),
                    "name": entry.get("im:name", {}).get("label"),
                    "developer": entry.get("im:artist", {}).get("label"),
                    "icon_url": icon_url,
                    "rank": i + 1,
                    "chart_type": chart_type,
                    "category_name": category_name,
                    "genre_id": genre_id_val,
                })

            logger.info(
                f"Top charts ({chart_slug}/genre={genre_id}): {len(results)} apps fetched"
            )
        except Exception as e:
            logger.error(f"Error fetching top charts ({chart_type}/{genre_id}): {e}")
        return results

    async def get_top_charts(self, chart_type: str = "topfree", category: str = None, limit: int = 200, country: str = "us") -> List[Dict]:
        genre_id = _category_to_genre_id(category)
        return await asyncio.to_thread(self._get_top_charts_sync, chart_type, genre_id, limit, country)


async def run_scraper_demo():
    scraper = AppStoreScraper()
    await scraper.init()

    try:
        print("Searching for 'productivity apps'...")
        results = await scraper.get_search_results("productivity", limit=10)
        print(f"Found {len(results)} apps")
        print(results[:3])

    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(run_scraper_demo())
