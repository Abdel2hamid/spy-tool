"""
App Store Search Scraper
========================
Uses Playwright to scrape real App Store search results including:
- Organic positions 1–20
- Sponsored (Apple Search Ads) detection
- App metadata: name, developer, icon, app_id
"""

import asyncio
import json
import logging
import re
import time
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Text patterns that indicate a sponsored/ad placement
SPONSORED_PATTERNS = [
    "sponsored",
    "search ads",
    "suggested by search ads",
    r"\bad\b",              # standalone "Ad"
]
_SPONSORED_RE = re.compile(
    "|".join(SPONSORED_PATTERNS), re.IGNORECASE
)

# JavaScript executed inside the browser to extract search results reliably
_EXTRACT_JS = """
() => {
    const results = [];
    const seen = new Set();

    // All links pointing to an App Store app page
    const links = [...document.querySelectorAll('a[href*="/app/"]')];

    for (const link of links) {
        const href = link.href || '';
        // App Store app hrefs: /us/app/<name>/id<digits>
        const idMatch = href.match(/\\/id(\\d{6,})/);
        if (!idMatch) continue;

        const appId = idMatch[1];
        if (seen.has(appId)) continue;
        seen.add(appId);

        // Walk up a few levels to find the card container
        let card = link;
        for (let i = 0; i < 6; i++) {
            if (!card.parentElement) break;
            card = card.parentElement;
        }
        const cardText = (card ? card.innerText : link.innerText) || '';

        // Sponsored detection — look in card text and data attributes
        const cardHtml = card ? card.innerHTML : '';
        const isSponsoredByText = /sponsored|search\\s+ads|\\bAd\\b/i.test(cardText);
        const isSponsoredByAttr = /sponsored|searchads|search-ads/i.test(
            card ? (card.getAttribute('data-testid') || card.getAttribute('data-type') || card.className || '') : ''
        );
        const isSponsored = isSponsoredByText || isSponsoredByAttr;

        // App name — prefer h3/h2 inside the link, fall back to first line of text
        let name = '';
        const heading = link.querySelector('h3, h2, h4, [class*="title"], [class*="name"]');
        if (heading) {
            name = heading.innerText.trim();
        } else {
            // First non-empty line in link text
            const lines = link.innerText.split('\\n').map(l => l.trim()).filter(Boolean);
            name = lines[0] || '';
        }

        // Developer name — second non-empty text line or subtitle element
        let developer = '';
        const subtitle = link.querySelector('[class*="subtitle"], [class*="developer"], [class*="author"]');
        if (subtitle) {
            developer = subtitle.innerText.trim();
        } else {
            const lines = link.innerText.split('\\n').map(l => l.trim()).filter(Boolean);
            developer = lines[1] || '';
        }

        // Icon — first img in the link; prefer srcset 1x entry or data-srcset
        const img = link.querySelector('img');
        let icon = '';
        if (img) {
            // Try srcset (e.g. "https://... 1x, https://... 2x") — take first entry
            const srcset = img.srcset || img.getAttribute('data-srcset') || '';
            if (srcset) {
                icon = srcset.split(',')[0].trim().split(' ')[0];
            }
            if (!icon || icon.includes('1x1.gif')) {
                icon = img.getAttribute('data-src') || img.src || '';
            }
        }

        results.push({
            app_id: appId,
            app_name: name,
            developer: developer,
            icon: icon,
            is_sponsored: isSponsored,
        });

        if (results.length >= 25) break;
    }

    return results;
}
"""


class AppStoreSearchScraper:
    """
    Playwright-based App Store search result scraper.

    Usage (async context manager):
        async with AppStoreSearchScraper() as scraper:
            result = await scraper.search("productivity", country="us")
    """

    SEARCH_URL = "https://apps.apple.com/{country}/search?q={term}"

    def __init__(self, headless: bool = True, timeout_ms: int = 30_000):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None

    async def __aenter__(self):
        await self._start()
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def _start(self):
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        logger.info("AppStoreSearchScraper: browser started")

    async def close(self):
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        logger.info("AppStoreSearchScraper: browser closed")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        keyword: str,
        country: str = "us",
        max_results: int = 20,
        retries: int = 2,
    ) -> Dict:
        """
        Scrape App Store search results for *keyword* in *country*.

        Returns::

            {
                "keyword": "ai photo",
                "country": "us",
                "captured_at": "2024-...",
                "results": [
                    {
                        "position": 1,
                        "app_id": "123456",
                        "app_name": "...",
                        "developer": "...",
                        "icon": "https://...",
                        "is_sponsored": True,
                    },
                    ...
                ]
            }
        """
        for attempt in range(retries + 1):
            try:
                return await self._scrape_once(keyword, country, max_results)
            except Exception as exc:
                if attempt < retries:
                    wait = 2 ** attempt
                    logger.warning(
                        f"Search attempt {attempt+1} failed for {keyword!r}: {exc} — retry in {wait}s"
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"All {retries+1} attempts failed for {keyword!r}: {exc}")
                    return self._empty_result(keyword, country)

    async def search_many(
        self,
        keywords: List[str],
        country: str = "us",
        max_results: int = 20,
        concurrency: int = 3,
    ) -> List[Dict]:
        """
        Scrape multiple keywords with bounded concurrency.
        Returns a list of result dicts (one per keyword).
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _bounded(kw: str) -> Dict:
            async with semaphore:
                result = await self.search(kw, country, max_results)
                await asyncio.sleep(1.5)  # polite delay between requests
                return result

        tasks = [asyncio.create_task(_bounded(kw)) for kw in keywords]
        return await asyncio.gather(*tasks)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _scrape_once(
        self,
        keyword: str,
        country: str,
        max_results: int,
    ) -> Dict:
        from playwright.async_api import TimeoutError as PWTimeout

        t0 = time.monotonic()
        url = self.SEARCH_URL.format(
            country=country.lower(),
            term=keyword.strip().replace(" ", "+"),
        )

        context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Safari/605.1.15"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        try:
            logger.info(f"[search] {keyword!r} / {country} → {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)

            # Wait for at least one app link to appear
            try:
                await page.wait_for_selector(
                    'a[href*="/app/"]',
                    timeout=20_000,
                    state="attached",
                )
            except PWTimeout:
                logger.warning(f"[search] Timeout waiting for results: {keyword!r}")
                return self._empty_result(keyword, country)

            # Scroll to trigger lazy-loaded images, then settle
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.0)
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1.0)

            # Execute JS extraction in the page context
            raw: List[Dict] = await page.evaluate(_EXTRACT_JS)

            # Post-process: assign positions, cap at max_results
            results = []
            organic_pos = 0
            ad_pos = 0

            for item in raw[:max_results]:
                # Additional Python-side sponsored check via app_name/developer text
                combined = f"{item.get('app_name','')} {item.get('developer','')}".lower()
                if _SPONSORED_RE.search(combined):
                    item["is_sponsored"] = True

                if item["is_sponsored"]:
                    ad_pos += 1
                    position = ad_pos  # sponsored positions are tracked separately
                else:
                    organic_pos += 1
                    position = organic_pos

                results.append({
                    "position": len(results) + 1,  # absolute position on page
                    "organic_position": None if item["is_sponsored"] else organic_pos,
                    "app_id": item["app_id"],
                    "app_name": item.get("app_name", ""),
                    "developer": item.get("developer", ""),
                    "icon": item.get("icon", ""),
                    "is_sponsored": item["is_sponsored"],
                })

            # Enrich with real icon URLs via iTunes Lookup (batch, async thread)
            app_ids = [r["app_id"] for r in results]
            icon_map = await asyncio.to_thread(self._fetch_icons, app_ids, country)
            for r in results:
                if icon_map.get(r["app_id"]):
                    r["icon"] = icon_map[r["app_id"]]

            elapsed = time.monotonic() - t0
            sponsored_count = sum(1 for r in results if r["is_sponsored"])
            logger.info(
                f"[search] {keyword!r}: {len(results)} results "
                f"({sponsored_count} sponsored) in {elapsed:.1f}s"
            )

            return {
                "keyword": keyword,
                "country": country,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "results": results,
            }

        finally:
            await context.close()

    @staticmethod
    def _fetch_icons(app_ids: List[str], country: str = "us") -> Dict[str, str]:
        """
        Batch-fetch artworkUrl100 from iTunes Lookup API for a list of app IDs.
        Returns a dict mapping app_id → icon_url.
        """
        if not app_ids:
            return {}
        try:
            ids_param = ",".join(app_ids[:50])  # max 50 per request
            url = f"https://itunes.apple.com/lookup?id={ids_param}&country={country}&entity=software"
            req = urllib.request.Request(url, headers={"User-Agent": "AppStoreSpy/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
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
            sp = " [SPONSORED]" if r["is_sponsored"] else ""
            print(f"  #{r['position']:>2}  {r['app_id']:<12}  {r['app_name'][:40]}{sp}")


if __name__ == "__main__":
    asyncio.run(_test())
