# scrapers/example_scraper.py
# ─────────────────────────────────────────────────────────────
# Example scraper — copy this file to build a new site scraper.
# Only parse() and start_urls need to change per site.
# ─────────────────────────────────────────────────────────────

from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper
from models.scraped_item import SalonProfile


class ExampleScraper(BaseScraper):
    name = "example"

    start_urls = [
        "https://example.com/page/1",
        "https://example.com/page/2",
    ]

    async def parse(self, html: str, url: str) -> SalonProfile:
        soup = BeautifulSoup(html, "html.parser")

        return SalonProfile(
            page_url   = url,
            salon_name = (soup.select_one(".salon-name") or {}).get_text(strip=True),
            staff_name = (soup.select_one(".staff-name") or {}).get_text(strip=True),
            location   = (soup.select_one(".address")    or {}).get_text(strip=True),
        )
