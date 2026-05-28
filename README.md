# Production-Grade Web Scraping System

A scalable, async, ethical web scraping framework using Python, Playwright,
PostgreSQL, and Redis — built with clean architecture and SOLID principles.

---

## Folder Structure

```
scraper_system/
├── main.py                        ← Entry point
├── requirements.txt
├── .env.example                   ← Copy to .env and fill in values
│
├── config/
│   └── settings.py                ← All config from environment variables
│
├── scrapers/
│   ├── base_scraper.py            ← Async HTTP scraper base (httpx + BS4)
│   ├── playwright_scraper.py      ← Browser-based base (JS-heavy sites)
│   ├── example_scraper.py         ← Template: copy for each new site
│   └── example_playwright.py      ← Template: copy for JS-heavy sites
│
├── middlewares/
│   ├── proxy_manager.py           ← Proxy pool, rotation, health checks
│   ├── rate_limiter.py            ← Per-domain token-bucket rate limiting
│   └── retry.py                   ← Exponential backoff retry decorator
│
├── models/
│   └── scraped_item.py            ← Pydantic data models with validation
│
├── db/
│   ├── connection.py              ← Async PostgreSQL connection pool
│   └── queries.py                 ← All SQL — upsert, migrations, dedup
│
├── workers/
│   ├── queue_manager.py           ← Redis task queue (enqueue/dequeue)
│   └── scraper_worker.py          ← Worker that pulls URLs from queue
│
├── exports/
│   └── exporter.py                ← Save results to JSON / CSV / XML
│
├── utils/
│   ├── logger.py                  ← Structured logging + secret masking
│   ├── robots.py                  ← robots.txt checker (cached per domain)
│   └── user_agents.py             ← Realistic UA pool with weighted rotation
│
├── logs/                          ← Auto-created log files
│
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env — fill in DB password, proxy credentials, etc.
```

### 3. Start services (Docker)
```bash
cd docker
docker-compose up -d postgres redis
```

### 4. Build your scraper
Copy `scrapers/example_scraper.py` (HTTP) or `scrapers/example_playwright.py` (JS sites):

```python
# scrapers/my_site_scraper.py
from scrapers.base_scraper import BaseScraper
from models.scraped_item import SalonProfile
from bs4 import BeautifulSoup

class MySiteScraper(BaseScraper):
    name = "my_site"
    start_urls = ["https://mysite.com/listing/1", ...]

    async def parse(self, html: str, url: str) -> SalonProfile:
        soup = BeautifulSoup(html, "html.parser")
        return SalonProfile(
            page_url   = url,
            salon_name = soup.select_one(".name").get_text(strip=True),
            location   = soup.select_one(".address").get_text(strip=True),
        )
```

### 5. Wire it into main.py and run
```python
from scrapers.my_site_scraper import MySiteScraper
scraper = MySiteScraper()
data, failures = await scraper.run()
```
```bash
python main.py
```

---

## Architecture: Why Each Component Exists

| Component | Why it exists |
|---|---|
| `config/settings.py` | Single source of truth — no `os.getenv` scattered through code |
| `middlewares/proxy_manager.py` | Rotate IPs to avoid rate-limiting and blocks |
| `middlewares/rate_limiter.py` | Throttle requests per domain — ethical and avoids bans |
| `middlewares/retry.py` | Exponential backoff — recovers from transient failures |
| `utils/robots.py` | Respect robots.txt — legal and ethical requirement |
| `utils/user_agents.py` | Rotate real browser UAs — reduces bot detection signals |
| `workers/queue_manager.py` | Redis queue — enables distributed workers + crash recovery |
| `models/scraped_item.py` | Pydantic validation — catches bad data before it hits the DB |
| `db/queries.py` | UPSERT pattern — safe to re-run, never creates duplicates |

---

## Proxy Configuration

### Option A — Rotating gateway (recommended for production)
```env
PROXY_GATEWAY_URL=http://gate.provider.com:7000
PROXY_USERNAME=user123
PROXY_PASSWORD=secret
```
One endpoint, the provider rotates IPs automatically.

### Option B — Static list
```env
PROXY_STATIC_LIST=http://user:pass@1.2.3.4:8080,http://user:pass@5.6.7.8:8080
```
System rotates through them and marks dead ones automatically.

### Country targeting
```env
PROXY_COUNTRY=JP   # prefer Japanese IPs
```

---

## Scaling Up

### More workers (single machine)
```env
SCRAPER_WORKERS=16
```

### Multiple machines (distributed)
1. All workers point to the same Redis and PostgreSQL
2. Start workers on each machine:
```bash
python -c "
import asyncio
from workers.scraper_worker import run_pool
from scrapers.my_site_scraper import MySiteScraper
asyncio.run(run_pool(MySiteScraper, num_workers=8))
"
```
3. One producer enqueues URLs:
```python
await queue_manager.enqueue_urls(["https://...", ...])
```

### Docker Compose (scale scraper containers)
```bash
docker-compose up --scale scraper=4
```

---

## Anti-Bot Measures Applied

| Measure | Where |
|---|---|
| User-agent rotation (weighted by real market share) | `utils/user_agents.py` |
| Per-domain rate limiting (token bucket) | `middlewares/rate_limiter.py` |
| Randomised delays between requests | `scrapers/base_scraper.py` |
| Proxy rotation with health checking | `middlewares/proxy_manager.py` |
| Playwright: webdriver flag removed | `scrapers/playwright_scraper.py` |
| Playwright: realistic viewport + locale | `scrapers/playwright_scraper.py` |
| Playwright: human-like scroll behaviour | `scrapers/playwright_scraper.py` |
| Retry with exponential backoff + jitter | `middlewares/retry.py` |

---

## Legal & Ethical Guidelines

### Always do
- ✅ Check `robots.txt` before crawling (built-in, enabled by default)
- ✅ Respect `Crawl-delay` directives
- ✅ Only scrape **publicly accessible** pages (no login walls)
- ✅ Identify your bot with a descriptive User-Agent when possible
- ✅ Store only the data you actually need
- ✅ Read the site's Terms of Service before scraping

### Never do
- ❌ Bypass authentication or login systems
- ❌ Scrape private user data (emails, personal info without consent)
- ❌ Ignore `robots.txt` (`SCRAPER_RESPECT_ROBOTS=true` must stay on)
- ❌ Send requests so fast you degrade site performance (rate limiting is your protection here)
- ❌ Scrape and republish copyrighted content commercially

### CAPTCHA
This system does **not** include CAPTCHA solving. Encountering a CAPTCHA means
the site is actively blocking bots — the ethical response is to slow down,
use residential proxies, or contact the site owner about API access.

### robots.txt example
```
User-agent: *
Disallow: /private/
Crawl-delay: 5
```
This system will skip `/private/` URLs and wait at least 5 seconds between
requests to that domain — automatically.

---

## Security Practices

- All credentials in `.env` — never in code
- Passwords are masked in all log output (`LOG_MASK_SECRETS=true`)
- Docker container runs as non-root user
- `.env` is in `.gitignore` — never committed
- DB uses parameterised queries — no SQL injection risk
- Connection pool uses SSL in production (`PGSSLMODE=require`)

---

## Common Mistakes to Avoid

1. **No rate limiting** → banned within minutes
2. **Ignoring robots.txt** → legal risk, ethical problem
3. **Hardcoding credentials** → security breach
4. **No retry logic** → one transient error loses the whole run
5. **No deduplication** → duplicate rows accumulate in DB
6. **Single User-Agent** → trivially detected and blocked
7. **No proxy health checks** → dead proxies silently cause all requests to fail
8. **Scraping behind login** → likely violates ToS and computer fraud laws

---

## Database

```sql
-- View all scraped data
SELECT * FROM scraped_profiles ORDER BY saved_at DESC;

-- Check failed URLs
SELECT * FROM failed_urls ORDER BY failed_at DESC;

-- Domain stats
SELECT domain, COUNT(*) FROM scraped_profiles GROUP BY domain;
```
#   s c r a p e r _ s y s t e m  
 