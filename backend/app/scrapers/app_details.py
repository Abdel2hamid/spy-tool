import asyncio
import json
import re
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import logging

from app.services.apple_http_client import apple_fetch, apple_fetch_json, ITUNES_LOOKUP_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AppStoreAppScraper:
    APPSTORE_BASE_URL = "https://apps.apple.com"

    def __init__(self):
        pass

    def _make_request_sync(self, url: str) -> Optional[str]:
        """Synchronous HTTP GET — always call via asyncio.to_thread from async code."""
        try:
            body = apple_fetch(url, timeout=30, headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
            if body is None:
                return None
            return body.decode("utf-8")
        except Exception as e:
            logger.error(f"Request failed for {url}: {e}")
            return None

    async def _make_request(self, url: str) -> Optional[str]:
        return await asyncio.to_thread(self._make_request_sync, url)

    async def _make_json_request(self, url: str) -> Optional[dict]:
        """Fetch JSON from a URL using the shared Apple HTTP client."""
        data = await asyncio.to_thread(apple_fetch_json, url, timeout=30)
        return data

    async def get_app_details(self, app_id: str, country: str = "us") -> Optional[Dict]:
        """
        Fetch app metadata using the iTunes Lookup API.
        Returns structured data including name, description, developer, icon,
        screenshots, categories, rating, reviews count, version, dates, etc.
        """
        url = f"{ITUNES_LOOKUP_URL}?id={app_id}&country={country}&entity=software"
        data = await self._make_json_request(url)

        if not data or not data.get("results"):
            logger.warning(f"No iTunes data found for app {app_id} (country={country})")
            return None

        try:
            r = data["results"][0]

            # Dates
            release_date = None
            if r.get("releaseDate"):
                try:
                    release_date = datetime.fromisoformat(r["releaseDate"].replace("Z", "+00:00"))
                except Exception:
                    pass

            last_updated = None
            if r.get("currentVersionReleaseDate"):
                try:
                    last_updated = datetime.fromisoformat(r["currentVersionReleaseDate"].replace("Z", "+00:00"))
                except Exception:
                    pass

            # Categories
            genres = r.get("genres", [])
            primary_category = r.get("primaryGenreName") or (genres[0] if genres else None)
            secondary_category = genres[1] if len(genres) > 1 else None

            # Screenshots: phone + iPad
            screenshots = r.get("screenshotUrls", []) + r.get("ipadScreenshotUrls", [])

            # Icon – highest resolution available
            icon_url = r.get("artworkUrl512") or r.get("artworkUrl100") or r.get("artworkUrl60")

            # In-app purchases (not always present in API)
            in_app_purchases = []
            for iap in r.get("inAppPurchasesCollection") or []:
                name = iap.get("name") or iap.get("localizedName")
                if name:
                    in_app_purchases.append(name)

            return {
                "app_id": app_id,
                "url": r.get("trackViewUrl", f"{self.APPSTORE_BASE_URL}/{country}/app/id{app_id}"),
                "name": r.get("trackName"),
                # 'subtitle' is present in some newer API responses
                "subtitle": r.get("subtitle"),
                "description": r.get("description"),
                "developer": r.get("sellerName") or r.get("artistName"),
                "developer_id": str(r.get("artistId", "")) or None,
                "icon_url": icon_url,
                "screenshots": screenshots,
                "primary_category": primary_category,
                "secondary_category": secondary_category,
                "is_free": r.get("price", 0) == 0,
                "price": r.get("price", 0),
                "currency": r.get("currency", "USD"),
                "in_app_purchases": in_app_purchases,
                "current_version": r.get("version"),
                "minimum_ios_version": r.get("minimumOsVersion"),
                "supported_languages": r.get("languageCodesISO2A", []),
                "release_date": release_date,
                "last_updated": last_updated,
                "content_rating": r.get("contentAdvisoryRating"),
                "current_rating": r.get("averageUserRating"),
                "current_reviews": r.get("userRatingCount", 0),
                # Used as fallback release notes for the current version
                "_current_release_notes": r.get("releaseNotes"),
            }

        except Exception as e:
            logger.error(f"Failed to parse iTunes data for {app_id}: {e}")
            return None

    async def get_app_versions(self, app_id: str, country: str = "us") -> List[Dict]:
        """
        Scrape version history from the App Store page.

        Strategy:
        1. Fetch the main app page (no ?see-all=versions needed).
        2. Find the embedded JSON in the <script> tag that contains
           mostRecentVersion.seeAllAction.pageData.shelves[0].items
           Each item has:
             primarySubtitle  → version number string
             secondarySubtitle → date string
             text             → release notes
        3. Fall back to BeautifulSoup selectors if JSON extraction fails.
        """
        url = f"{self.APPSTORE_BASE_URL}/{country}/app/id{app_id}"
        html = await self._make_request(url)

        if not html:
            return []

        versions = []

        # ── Strategy 1: embedded JSON ──────────────────────────────────
        try:
            soup = BeautifulSoup(html, "html.parser")
            for script in soup.find_all("script"):
                src = script.string or ""
                if "versionHistory" not in src:
                    continue

                # The JSON blob starts at the first '{' in the script tag
                start = src.find("{")
                if start == -1:
                    continue
                try:
                    data = json.loads(src[start:])
                except Exception:
                    continue

                # Recursively find 'mostRecentVersion' (path varies by storefront)
                def _find_key(obj, key, depth=0):
                    if depth > 12:
                        return None
                    if isinstance(obj, dict):
                        if key in obj:
                            return obj[key]
                        for v in obj.values():
                            r = _find_key(v, key, depth + 1)
                            if r is not None:
                                return r
                    elif isinstance(obj, list):
                        for item in obj:
                            r = _find_key(item, key, depth + 1)
                            if r is not None:
                                return r
                    return None

                items = None
                try:
                    mrv = _find_key(data, "mostRecentVersion")
                    if mrv:
                        shelves = mrv.get("seeAllAction", {}).get("pageData", {}).get("shelves", [])
                        if shelves:
                            items = shelves[0].get("items", [])
                except Exception:
                    pass

                if not items:
                    continue

                for i, item in enumerate(items):
                    version_str = item.get("primarySubtitle", "")
                    date_str = item.get("secondarySubtitle", "")
                    notes = item.get("text", "")

                    if not version_str:
                        continue

                    # Clean version string (sometimes prefixed with app name line)
                    match = re.search(r"(\d+\.\d+(?:\.\d+)*)", version_str)
                    version_num = match.group(1) if match else version_str

                    release_date = None
                    if date_str:
                        try:
                            # Format: "Thu Mar 05 2026 10:54:19 GMT+0000 (...)"
                            # Strip the timezone description in parens
                            clean = re.sub(r"\s*\(.*?\)\s*$", "", date_str).strip()
                            release_date = datetime.strptime(clean, "%a %b %d %Y %H:%M:%S GMT%z")
                        except Exception:
                            try:
                                release_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            except Exception:
                                pass

                    versions.append({
                        "version": version_num,
                        "release_date": release_date,
                        "release_notes": notes.strip() if notes else None,
                        "is_latest": i == 0,
                    })

                if versions:
                    logger.info(f"Extracted {len(versions)} versions from embedded JSON for {app_id}")
                    return versions[:50]

        except Exception as e:
            logger.error(f"JSON version extraction failed for {app_id}: {e}")

        # ── Strategy 2: legacy HTML selectors (fallback) ──────────────
        try:
            soup = BeautifulSoup(html, "html.parser")
            version_items = (
                soup.find_all("li", {"class": lambda x: x and "version-history__item" in x})
                or soup.find_all("div", {"class": lambda x: x and "version-history__item" in x})
            )
            for item in version_items:
                version_data: Dict = {"version": None, "release_date": None, "release_notes": None, "is_latest": False}
                ver_elem = item.find("h3") or item.find(class_=lambda x: x and "version-number" in (x if isinstance(x, str) else " ".join(x)))
                if ver_elem:
                    m = re.search(r"(\d+\.\d+(?:\.\d+)*)", ver_elem.get_text(strip=True))
                    version_data["version"] = m.group(1) if m else ver_elem.get_text(strip=True)
                date_elem = item.find("time")
                if date_elem:
                    try:
                        version_data["release_date"] = datetime.fromisoformat(
                            (date_elem.get("datetime") or date_elem.get_text(strip=True)).replace("Z", "+00:00")
                        )
                    except Exception:
                        pass
                if version_data["version"]:
                    versions.append(version_data)
            if versions:
                versions[0]["is_latest"] = True
        except Exception as e:
            logger.error(f"HTML version extraction failed for {app_id}: {e}")

        return versions[:50]

    async def get_app_reviews(self, app_id: str, country: str = "us", limit: int = 50) -> List[Dict]:
        """
        Fetch reviews via the iTunes RSS API.
        Returns review_id, user_name, rating, title, content, date,
        app_version, storefront, developer_reply fields.
        """
        reviews = []

        # The feed serves ~50 reviews per page and hard-caps at page 10
        max_page = min((limit + 49) // 50, 10)
        for page in range(1, max_page + 1):
            url = (
                f"https://itunes.apple.com/{country}/rss/customerreviews"
                f"/page={page}/id={app_id}/sortby=mostrecent/json"
            )

            try:
                raw = await self._make_request(url)
                if not raw:
                    break
                data = json.loads(raw)

                if "feed" not in data or "entry" not in data["feed"]:
                    break

                entries = data["feed"]["entry"]
                # Single-entry feeds return a dict instead of list
                if isinstance(entries, dict):
                    entries = [entries]

                for entry in entries:
                    entry_id = entry.get("id", {}).get("label", "")
                    # Skip the app-info entry: real reviews always carry im:rating
                    if not entry_id or "im:rating" not in entry:
                        continue

                    review = {
                        "review_id": entry_id.split("/")[-1],
                        "user_name": entry.get("author", {}).get("name", {}).get("label", "Unknown"),
                        "user_url": entry.get("author", {}).get("uri", {}).get("label", ""),
                        "rating": int(entry.get("im:rating", {}).get("label", 0) or 0),
                        "title": entry.get("title", {}).get("label", ""),
                        "content": entry.get("content", {}).get("label", ""),
                        "date": entry.get("updated", {}).get("label", ""),
                        "app_version": entry.get("im:version", {}).get("label", ""),
                        "storefront": country.upper(),
                        "developer_reply_text": None,
                        "developer_reply_date": None,
                        "helpful_count": 0,
                    }

                    date_str = review["date"]
                    if date_str:
                        try:
                            review["date"] = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        except Exception:
                            review["date"] = None

                    reviews.append(review)

                    if len(reviews) >= limit:
                        break

            except Exception as e:
                logger.error(f"Failed to fetch reviews page {page} for {app_id}: {e}")
                break

            if len(reviews) >= limit:
                break

            await asyncio.sleep(0.5)  # Avoid rate limiting

        return reviews[:limit]

    async def _scrape_page_metadata(self, app_id: str, country: str = "us") -> Dict:
        """
        Scrape the App Store HTML page for metadata that the iTunes API
        doesn't provide: subtitle and screenshot URLs.

        The page embeds JSON data in <script> tags that contain fields like
        'subtitle' and screenshot image sources.
        """
        url = f"{self.APPSTORE_BASE_URL}/{country}/app/id{app_id}"
        html = await self._make_request(url)
        if not html:
            return {}

        result: Dict = {}
        try:
            soup = BeautifulSoup(html, "html.parser")

            # ── Extract from embedded JSON in script tags ────────────
            for script in soup.find_all("script"):
                src = script.string or ""
                if len(src) < 200:
                    continue

                start = src.find("{")
                if start == -1:
                    continue

                try:
                    data = json.loads(src[start:])
                except Exception:
                    continue

                # Recursively find fields we need
                def _find_all(obj, key, depth=0, results=None):
                    if results is None:
                        results = []
                    if depth > 15:
                        return results
                    if isinstance(obj, dict):
                        if key in obj and obj[key]:
                            results.append(obj[key])
                        for v in obj.values():
                            _find_all(v, key, depth + 1, results)
                    elif isinstance(obj, list):
                        for item in obj[:50]:
                            _find_all(item, key, depth + 1, results)
                    return results

                # Subtitle
                if not result.get("subtitle"):
                    subtitles = _find_all(data, "subtitle")
                    for s in subtitles:
                        if isinstance(s, str) and 3 < len(s) < 100:
                            result["subtitle"] = s
                            break

                # Screenshots: look for screenshot URLs in the JSON
                if not result.get("screenshots"):
                    # Try screenshotsByType structure
                    ss_by_type = _find_all(data, "screenshotsByType")
                    for ss_map in ss_by_type:
                        if isinstance(ss_map, dict):
                            urls = []
                            for _type_key, ss_list in ss_map.items():
                                if isinstance(ss_list, list):
                                    for ss in ss_list:
                                        if isinstance(ss, dict) and ss.get("url"):
                                            urls.append(ss["url"])
                                        elif isinstance(ss, str) and "mzstatic.com" in ss:
                                            urls.append(ss)
                            if urls:
                                result["screenshots"] = urls
                                break

                if result.get("subtitle") and result.get("screenshots"):
                    break

            # ── Fallback: extract screenshot URLs from img/source tags ──
            if not result.get("screenshots"):
                ss_urls = []
                for tag in soup.find_all(["img", "source"]):
                    src_attr = tag.get("srcset") or tag.get("src") or ""
                    if "mzstatic.com" in src_attr and "screen" in src_attr.lower():
                        # srcset may have multiple URLs; take the first
                        url_part = src_attr.split(",")[0].split(" ")[0].strip()
                        if url_part and url_part not in ss_urls:
                            ss_urls.append(url_part)
                if ss_urls:
                    result["screenshots"] = ss_urls

        except Exception as e:
            logger.warning(f"Page metadata scrape failed for {app_id}: {e}")

        if result.get("subtitle"):
            logger.info(f"Scraped subtitle for {app_id}: {result['subtitle']}")
        if result.get("screenshots"):
            logger.info(f"Scraped {len(result['screenshots'])} screenshots for {app_id}")

        return result

    async def scrape_full_app_data(self, app_id: str, country: str = "us") -> Dict:
        """
        Fetch and return all data for an app:
        - app_details (metadata, rating, reviews count, etc.)
        - versions (version history; falls back to current version from iTunes)
        - reviews (up to 50 most recent)
        """
        result: Dict = {
            "app_details": None,
            "versions": [],
            "reviews": [],
        }

        logger.info(f"Scraping app {app_id} (country={country})...")

        details = await self.get_app_details(app_id, country)
        if details:
            result["app_details"] = details
            logger.info(f"Got details for {app_id}: {details.get('name')}")
        else:
            logger.warning(f"No details returned for app {app_id}, aborting full scrape")
            return result

        # If iTunes API didn't provide subtitle or screenshots, scrape the page
        has_subtitle = bool(details.get("subtitle"))
        has_screenshots = bool(details.get("screenshots"))

        if not has_subtitle or not has_screenshots:
            await asyncio.sleep(0.5)
            page_meta = await self._scrape_page_metadata(app_id, country)
            if page_meta.get("subtitle") and not has_subtitle:
                details["subtitle"] = page_meta["subtitle"]
            if page_meta.get("screenshots") and not has_screenshots:
                details["screenshots"] = page_meta["screenshots"]

        await asyncio.sleep(0.5)

        versions = await self.get_app_versions(app_id, country)
        if versions:
            result["versions"] = versions
            logger.info(f"Got {len(versions)} versions for {app_id}")
        elif details.get("current_version"):
            # Fallback: synthesise a single version entry from iTunes API data
            result["versions"] = [{
                "version": details["current_version"],
                "release_date": details.get("last_updated"),
                "release_notes": details.get("_current_release_notes"),
                "is_latest": True,
            }]
            logger.info(f"Using iTunes current version as version fallback for {app_id}")

        await asyncio.sleep(0.5)

        reviews = await self.get_app_reviews(app_id, country, limit=50)
        if reviews:
            result["reviews"] = reviews
            logger.info(f"Got {len(reviews)} reviews for {app_id}")

        return result


# ---------------------------------------------------------------------------
# Standalone helper (used outside of the worker, e.g. scripts / tests)
# ---------------------------------------------------------------------------

async def scrape_and_save_app(app_id: str, db_session, country: str = "us"):
    from app.models import models

    scraper = AppStoreAppScraper()
    data = await scraper.scrape_full_app_data(app_id, country)

    if not data["app_details"]:
        logger.error(f"Failed to scrape app {app_id}")
        return None

    details = data["app_details"]

    app = db_session.query(models.App).filter(models.App.app_id == app_id).first()
    if not app:
        app = models.App(app_id=app_id)
        db_session.add(app)

    app.name = details.get("name", app.name)
    app.subtitle = details.get("subtitle")
    app.description = details.get("description")
    app.developer = details.get("developer")
    app.developer_id = details.get("developer_id")
    app.icon_url = details.get("icon_url")
    app.screenshots = details.get("screenshots")
    app.primary_category = details.get("primary_category")
    app.secondary_category = details.get("secondary_category")
    app.is_free = details.get("is_free", True)
    app.price = details.get("price", 0)
    app.currency = details.get("currency", "USD")
    iap = details.get("in_app_purchases")
    app.in_app_purchases = (iap if isinstance(iap, bool) else bool(iap)) if iap not in (None, "", "[]") else False
    app.current_version = details.get("current_version")
    app.minimum_ios_version = details.get("minimum_ios_version")
    app.supported_languages = details.get("supported_languages")
    app.content_rating = details.get("content_rating")
    app.current_rating = details.get("current_rating")
    app.current_reviews = details.get("current_reviews", 0)
    app.url = details.get("url")

    if details.get("release_date"):
        app.release_date = details["release_date"]
    if details.get("last_updated"):
        app.last_updated = details["last_updated"]

    db_session.commit()

    # Reset is_latest before saving new version batch
    db_session.query(models.AppVersion).filter(models.AppVersion.app_id == app.id).update({"is_latest": False})
    db_session.commit()

    for version_data in data.get("versions", []):
        existing = db_session.query(models.AppVersion).filter(
            models.AppVersion.app_id == app.id,
            models.AppVersion.version == version_data.get("version"),
        ).first()

        if existing:
            existing.is_latest = version_data.get("is_latest", False)
        else:
            version = models.AppVersion(
                app_id=app.id,
                version=version_data.get("version"),
                release_date=version_data.get("release_date"),
                release_notes=version_data.get("release_notes"),
                is_latest=version_data.get("is_latest", False),
            )
            db_session.add(version)

    db_session.commit()

    for review_data in data.get("reviews", []):
        existing = db_session.query(models.Review).filter(
            models.Review.review_id == review_data.get("review_id")
        ).first()

        if not existing:
            review = models.Review(
                app_id=app.id,
                review_id=review_data.get("review_id"),
                user_name=review_data.get("user_name"),
                user_url=review_data.get("user_url"),
                rating=review_data.get("rating"),
                title=review_data.get("title"),
                content=review_data.get("content"),
                date=review_data.get("date"),
                app_version=review_data.get("app_version"),
                storefront=review_data.get("storefront"),
                developer_reply_text=review_data.get("developer_reply_text"),
                developer_reply_date=review_data.get("developer_reply_date"),
                helpful_count=review_data.get("helpful_count", 0),
            )
            db_session.add(review)

    db_session.commit()

    logger.info(
        f"Saved app {app_id} with {len(data.get('versions', []))} versions "
        f"and {len(data.get('reviews', []))} reviews"
    )

    return app


if __name__ == "__main__":
    async def test():
        scraper = AppStoreAppScraper()
        result = await scraper.scrape_full_app_data("1225155794")
        print(json.dumps(result, indent=2, default=str))

    asyncio.run(test())
