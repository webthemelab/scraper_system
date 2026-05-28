# main.py
# Run: python main.py
import asyncio
import sys

from db.queries import run_migrations, save_profiles, save_failed_urls
from db.connection import close_pool
from exports.exporter import save_json, save_csv, save_xml, save_failures
from config.settings import settings
from utils.logger import get_logger

log = get_logger("main")


async def main():
    log.info("=" * 55)
    log.info("Scraper system starting")
    log.info("=" * 55)

    # 1. Database setup
    try:
        await run_migrations()
    except Exception as e:
        log.error(f"DB connection failed: {e}")
        log.error("Check .env and make sure PostgreSQL is running.")
        sys.exit(1)

    # 2. Import your scraper here
    # ── Example with the async HTTP scraper ──
    # from scrapers.example_scraper import ExampleScraper
    # scraper = ExampleScraper()

    # ── Example with Playwright ──
    # from scrapers.example_playwright import ExamplePlaywrightScraper
    # scraper = ExamplePlaywrightScraper()

    # ── Example with queue-based workers ──
    # from workers.scraper_worker import run_pool
    # from scrapers.example_scraper import ExampleScraper
    # await run_pool(ExampleScraper, num_workers=settings.scraper.workers)
    # return

    # 3. Run
    # data, failures = await scraper.run()

    # 4. Export flat files
    # if data:
    #     save_json(data)
    #     save_csv(data)
    #     save_xml(data)
    # if failures:
    #     save_failures(failures)

    # 5. Save to DB
    # await save_profiles(data)
    # await save_failed_urls(failures)

    # 6. Summary
    # log.info("=" * 55)
    # log.info(f"Scraped  : {len(data)}")
    # log.info(f"Failed   : {len(failures)}")
    # log.info("=" * 55)

    log.info("System ready. Uncomment your scraper in main.py to start.")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
