# scrapers/base_scraper.py
# ─────────────────────────────────────────────────────────────
# Abstract base class for all scrapers.
#
# Every scraper inherits from this and only needs to implement:
#   • start_urls  — list of seed URLs
#   • parse()     — how to extract data from one page
#
# This class handles automatically:
#   • robots.txt checking
#   • Rate limiting (per domain)
#   • Proxy rotation
#   • User-agent rotation
#   • Retry with exponential backoff
#   • Randomised human-like delays
#   • Structured logging
#   • Failure tracking
# ─────────────────────────────────────────────────────────────

import asyncio
import random
from abc import ABC, abstractmethod
from typing import List, Tuple

import httpx
from bs4 import BeautifulSoup

from config.settings import settings
from middlewares.proxy_manager import proxy_manager
from middlewares.rate_limiter import rate_limiter
from middlewares.retry import with_retry, MaxRetriesExceeded, RETRYABLE_STATUSES
from models.scraped_item import ScrapedItem, FailedURL
from utils.logger import get_logger
from utils.robots import is_allowed
from utils.user_agents import get_weighted_ua


class BaseScraper(ABC):
    """
    Inherit from this to build a scraper for any website.

    Minimum required in subclass:
        start_urls = ["https://example.com/page1", ...]

        async def parse(self, html: str, url: str) -> ScrapedItem:
            soup = BeautifulSoup(html, "html.parser")
            return MyModel(page_url=url, title=soup.h1.text)
    """

    start_urls: List[str] = []
    name: str = "base"

    def __init__(self):
        self.log = get_logger(self.name)
        self._data: List[ScrapedItem] = []
        self._failures: List[FailedURL] = []

    # ── Must implement ────────────────────────────────────────

    @abstractmethod
    async def parse(self, html: str, url: str) -> ScrapedItem:
        """Extract data from one page's HTML and return a validated model."""
        ...

    # ── Optional overrides ────────────────────────────────────

    async def get_urls(self) -> List[str]:
        """
        Override to build the URL list dynamically (e.g. from a DB query
        or by crawling a sitemap). Default returns start_urls.
        """
        return self.start_urls

    # ── Core fetch ────────────────────────────────────────────

    async def _fetch(self, url: str, proxy: str | None = None) -> str:
        """Fetch one URL and return the response HTML."""
        headers = {"User-Agent": get_weighted_ua()}
        proxy_map = {"http://": proxy, "https://": proxy} if proxy else None

        async with httpx.AsyncClient(
            proxies=proxy_map,
            headers=headers,
            timeout=settings.scraper.timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)

            if resp.status_code in RETRYABLE_STATUSES:
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            return resp.text

    async def _fetch_with_proxy(self, url: str) -> str:
        """Fetch with automatic proxy rotation and retry."""
        proxy = proxy_manager.get_proxy()
        try:
            html = await self._fetch(url, proxy=proxy)
            if proxy:
                proxy_manager.report_success(proxy)
            return html
        except Exception:
            if proxy:
                proxy_manager.report_failure(proxy)
            raise

    # ── Main loop ─────────────────────────────────────────────

    async def scrape_one(self, url: str) -> ScrapedItem | None:
        """
        Scrape a single URL: check robots, rate-limit, fetch, parse.
        Returns None on failure (failure is logged internally).
        """
        # 1. robots.txt check
        if settings.scraper.respect_robots and not is_allowed(url):
            self.log.warning(f"Skipped (robots.txt): {url}")
            return None

        # 2. Rate limiting
        await rate_limiter.acquire(url)

        # 3. Human-like random delay
        delay = random.uniform(settings.scraper.delay_min, settings.scraper.delay_max)
        await asyncio.sleep(delay)

        # 4. Fetch (with retry)
        html = None
        for attempt in range(1, settings.scraper.max_retries + 1):
            proxy = proxy_manager.get_proxy()
            try:
                html = await self._fetch(url, proxy=proxy)
                if proxy:
                    proxy_manager.report_success(proxy)
                break
            except Exception as exc:
                if proxy:
                    proxy_manager.report_failure(proxy)
                if attempt == settings.scraper.max_retries:
                    self.log.error(f"✗ Failed after {attempt} attempts: {url} — {exc}")
                    self._failures.append(FailedURL(
                        url=url,
                        error_type=type(exc).__name__,
                        status=str(getattr(getattr(exc, "response", None), "status_code", None)),
                        message=str(exc),
                        scraper_name=self.name,
                    ))
                    return None
                backoff = (settings.scraper.retry_backoff ** attempt) + random.uniform(0, 0.5)
                self.log.warning(f"Attempt {attempt} failed ({exc}), retry in {backoff:.1f}s")
                await asyncio.sleep(backoff)

        # 5. Parse
        try:
            item = await self.parse(html, url)
            self.log.info(f"✓ {url}")
            return item
        except Exception as exc:
            self.log.error(f"✗ Parse error on {url}: {exc}")
            self._failures.append(FailedURL(
                url=url,
                error_type="parse_error",
                message=str(exc),
                scraper_name=self.name,
            ))
            return None

    async def run(self, urls: List[str] | None = None) -> Tuple[List[ScrapedItem], List[FailedURL]]:
        """
        Scrape all URLs concurrently up to the configured worker limit.

        Args:
            urls: Override URL list (default: self.start_urls / get_urls())

        Returns:
            (data, failures) — same contract expected by main.py
        """
        url_list = urls or await self.get_urls()
        # Deduplicate while preserving order
        url_list = list(dict.fromkeys(url_list))

        self.log.info(f"Starting {self.name} — {len(url_list)} URLs, "
                      f"{settings.scraper.workers} workers")

        semaphore = asyncio.Semaphore(settings.scraper.workers)

        async def _worker(url: str):
            async with semaphore:
                item = await self.scrape_one(url)
                if item:
                    self._data.append(item)

        await asyncio.gather(*[_worker(u) for u in url_list])

        self.log.info(f"Done — {len(self._data)} ok, {len(self._failures)} failed")
        return self._data, self._failures
