import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AppStoreScraper:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.base_url = "https://apps.apple.com"
    
    async def init(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        )
    
    async def close(self):
        if self.browser:
            await self.browser.close()
    
    async def get_search_results(self, keyword: str, limit: int = 50) -> List[Dict]:
        results = []
        try:
            search_url = f"{self.base_url}/us/search?term={keyword.replace(' ', '+')}&entity=software"
            await self.page.goto(search_url, wait_until="networkidle", timeout=30000)
            
            await self.page.wait_for_selector(".app-card", timeout=30000)
            
            cards = await self.page.query_selector_all(".app-card")[:limit]
            
            for i, card in enumerate(cards):
                try:
                    name_elem = await card.query_selector(".app-card__title")
                    name = await name_elem.inner_text() if name_elem else f"App {i+1}"
                    
                    developer_elem = await card.query_selector(".app-card__subtitle")
                    developer = await developer_elem.inner_text() if developer_elem else "Unknown"
                    
                    icon_elem = await card.query_selector("picture img")
                    icon_url = await icon_elem.get_attribute("src") if icon_elem else None
                    
                    link_elem = await card.query_selector("a")
                    app_link = await link_elem.get_attribute("href") if link_elem else None
                    
                    app_id = app_link.split("/")[-1].split("?")[0] if app_link else f"search_{keyword}_{i}"
                    
                    rating_elem = await card.query_selector(".we-rating-number")
                    rating = await rating_elem.inner_text() if rating_elem else None
                    
                    results.append({
                        "app_id": app_id,
                        "name": name.strip(),
                        "developer": developer.strip(),
                        "icon_url": icon_url,
                        "rating": float(rating) if rating else None,
                        "rank": i + 1,
                        "keyword": keyword
                    })
                except Exception as e:
                    logger.warning(f"Error parsing card {i}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error searching for {keyword}: {e}")
        
        return results
    
    async def get_top_charts(self, chart_type: str = "topfree", category: str = None, limit: int = 100) -> List[Dict]:
        results = []
        try:
            if category:
                url = f"{self.base_url}/us/ios/{category}/{chart_type}"
            else:
                url = f"{self.base_url}/us/ios/top/{chart_type}"
            
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            await self.page.wait_for_selector(".app-chart-item", timeout=30000)
            
            items = await self.page.query_selector_all(".app-chart-item")[:limit]
            
            for i, item in enumerate(items):
                try:
                    name_elem = await item.query_selector(".app-chart-item__title")
                    name = await name_elem.inner_text() if name_elem else f"App {i+1}"
                    
                    developer_elem = await item.query_selector(".app-chart-item__subtitle")
                    developer = await developer_elem.inner_text() if developer_elem else "Unknown"
                    
                    icon_elem = await item.query_selector("picture img")
                    icon_url = await icon_elem.get_attribute("src") if icon_elem else None
                    
                    rank_elem = await item.query_selector(".app-chart-item__rank")
                    rank_text = await rank_elem.inner_text() if rank_elem else str(i + 1)
                    rank = int(rank_text.replace("#", "").strip())
                    
                    link_elem = await item.query_selector("a")
                    app_link = await link_elem.get_attribute("href") if link_elem else None
                    
                    app_id = app_link.split("/")[-1].split("?")[0] if app_link else f"chart_{i}"
                    
                    results.append({
                        "app_id": app_id,
                        "name": name.strip(),
                        "developer": developer.strip(),
                        "icon_url": icon_url,
                        "rank": rank,
                        "chart_type": chart_type,
                        "category": category
                    })
                except Exception as e:
                    logger.warning(f"Error parsing chart item {i}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error fetching top charts: {e}")
        
        return results
    
    async def get_app_details(self, app_id: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/us/app/id{app_id}"
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            name_elem = await self.page.query_selector("h1.product-header-title")
            name = await name_elem.inner_text() if name_elem else None
            
            developer_elem = await self.page.query_selector("a.product-header__identity__name")
            developer = await developer_elem.inner_text() if developer_elem else None
            
            icon_elem = await self.page.query_selector("picture.product-header__image img")
            icon_url = await icon_elem.get_attribute("src") if icon_elem else None
            
            price_elem = await self.page.query_selector("li.app-header__list__item--price")
            price_text = await price_elem.inner_text() if price_elem else "Free"
            
            rating_elem = await self.page.query_selector("span.we-rating-number")
            rating = await rating_elem.inner_text() if rating_elem else None
            
            reviews_elem = await self.page.query_selector("span.hypertoken")
            reviews_text = await reviews_elem.inner_text() if reviews_elem else "0"
            
            description_elem = await self.page.query_selector("p.product-header__description")
            description = await description_elem.inner_text() if description_elem else None
            
            return {
                "app_id": app_id,
                "name": name.strip() if name else None,
                "developer": developer.strip() if developer else None,
                "icon_url": icon_url,
                "price": price_text.strip(),
                "rating": float(rating) if rating else None,
                "reviews": int(reviews_text.replace(",", "").replace(",", "")) if reviews_text else 0,
                "description": description.strip() if description else None,
                "scraped_at": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error fetching app details for {app_id}: {e}")
            return None
    
    async def get_reviews(self, app_id: str, limit: int = 50) -> List[Dict]:
        reviews = []
        try:
            url = f"{self.base_url}/us/app/id{app_id}?page=1"
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            await self.page.wait_for_selector(".ember-view", timeout=30000)
            
            review_cards = await self.page.query_selector_all(".ember-view")[:limit]
            
            for card in review_cards:
                try:
                    rating_elem = await card.query_selector(".we-rating-number")
                    rating = await rating_elem.inner_text() if rating_elem else None
                    
                    title_elem = await card.query_selector(".review-title")
                    title = await title_elem.inner_text() if title_elem else None
                    
                    content_elem = await card.query_selector(".review-content")
                    content = await content_elem.inner_text() if content_elem else None
                    
                    if rating:
                        reviews.append({
                            "app_id": app_id,
                            "review_id": f"{app_id}_{len(reviews)}",
                            "rating": float(rating),
                            "title": title.strip() if title else None,
                            "content": content.strip() if content else None,
                            "date": datetime.utcnow()
                        })
                except Exception:
                    continue
            
        except Exception as e:
            logger.error(f"Error fetching reviews for {app_id}: {e}")
        
        return reviews


async def run_scraper_demo():
    scraper = AppStoreScraper()
    await scraper.init()
    
    try:
        print("Searching for 'productivity apps'...")
        results = await scraper.get_search_results("productivity", limit=10)
        print(f"Found {len(results)} apps")
        
        print("\nFetching top charts...")
        charts = await scraper.get_top_charts("topfree", limit=10)
        print(f"Found {len(charts)} chart apps")
        
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(run_scraper_demo())
