# db/queries.py
# ─────────────────────────────────────────────────────────────
# All database operations — schema creation, upsert, and
# failure logging.  No raw SQL lives anywhere else in the code.
# ─────────────────────────────────────────────────────────────

from typing import List
from db.connection import get_pool
from models.scraped_item import SalonProfile, FailedURL
from utils.logger import get_logger

log = get_logger("db.queries")

# ── Schema ────────────────────────────────────────────────────

MIGRATIONS = [
    # 001 — core tables
    """
    CREATE TABLE IF NOT EXISTS scraped_profiles (
        page_url      TEXT PRIMARY KEY,
        domain        TEXT,
        scraper_name  TEXT,
        salon_name    TEXT,
        salon_kana    TEXT,
        staff_name    TEXT,
        rating        TEXT,
        location      TEXT,
        phone_number  TEXT,
        updated_date  TEXT,
        scraped_at    TIMESTAMPTZ DEFAULT NOW(),
        saved_at      TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS failed_urls (
        id            SERIAL PRIMARY KEY,
        url           TEXT NOT NULL,
        error_type    TEXT,
        status        TEXT,
        message       TEXT,
        scraper_name  TEXT,
        failed_at     TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    # 002 — indexes for common query patterns
    "CREATE INDEX IF NOT EXISTS idx_profiles_domain      ON scraped_profiles(domain);",
    "CREATE INDEX IF NOT EXISTS idx_profiles_scraped_at  ON scraped_profiles(scraped_at);",
    "CREATE INDEX IF NOT EXISTS idx_failed_url           ON failed_urls(url);",
]

# ── Upsert SQL ────────────────────────────────────────────────

UPSERT_PROFILE = """
    INSERT INTO scraped_profiles (
        page_url, domain, scraper_name,
        salon_name, salon_kana, staff_name,
        rating, location, phone_number, updated_date, scraped_at
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
    ON CONFLICT (page_url) DO UPDATE SET
        salon_name    = EXCLUDED.salon_name,
        salon_kana    = EXCLUDED.salon_kana,
        staff_name    = EXCLUDED.staff_name,
        rating        = EXCLUDED.rating,
        location      = EXCLUDED.location,
        phone_number  = EXCLUDED.phone_number,
        updated_date  = EXCLUDED.updated_date,
        scraped_at    = EXCLUDED.scraped_at,
        saved_at      = NOW();
"""

INSERT_FAILED = """
    INSERT INTO failed_urls (url, error_type, status, message, scraper_name)
    VALUES ($1, $2, $3, $4, $5);
"""


# ── Public functions ──────────────────────────────────────────

async def run_migrations():
    """Create tables and indexes. Safe to run on every startup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        for sql in MIGRATIONS:
            await conn.execute(sql)
    log.info("DB migrations applied")


async def save_profiles(profiles: List[SalonProfile]):
    """
    Upsert a batch of profiles.  Running this twice on the same
    URL updates the row — it never creates duplicates.
    """
    if not profiles:
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(
            UPSERT_PROFILE,
            [
                (
                    p.page_url, p.domain, p.scraper_name,
                    p.salon_name, p.salon_kana, p.staff_name,
                    p.rating, p.location, p.phone_number,
                    p.updated_date, p.scraped_at,
                )
                for p in profiles
            ],
        )
    log.info(f"Saved {len(profiles)} profiles to DB")


async def save_failed_urls(failures: List[FailedURL]):
    """Log failed URLs for later investigation or retry."""
    if not failures:
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(
            INSERT_FAILED,
            [
                (f.url, f.error_type, f.status, f.message, f.scraper_name)
                for f in failures
            ],
        )
    log.info(f"Logged {len(failures)} failed URLs")


async def url_already_scraped(url: str) -> bool:
    """
    Incremental scraping: return True if this URL is already in
    the database.  Use this to skip re-scraping unchanged pages.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM scraped_profiles WHERE page_url = $1", url
        )
    return row is not None
