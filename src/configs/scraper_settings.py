from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel


@dataclass
class DataPaths:
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    REGIONS_PATH: Path = BASE_DIR / "maps_data" / "regions.csv"
    RUBRICS_PATH: Path = BASE_DIR / "maps_data" / "rubrics.json"
    ENV_PATH: Path = BASE_DIR / ".env"


class ScrapySettings(BaseModel):
    # --- Basic limits and delays ---
    DOWNLOAD_DELAY: float = 1.5
    DOWNLOAD_MAXSIZE: int = 10_000_000
    CONCURRENT_REQUESTS: int = 4
    CONCURRENT_REQUESTS_PER_DOMAIN: int = 1
    CONTACTS_CSV_PATH: Path = DataPaths.BASE_DIR / "maps_data" / "contacts" / "final_2gis.csv"
    DOWNLOAD_TIMEOUT: int = 25

    # --- Infrastructure ---
    TWISTED_REACTOR: str = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

    DOWNLOAD_HANDLERS: dict[str, str] = {
        "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    }

    DOWNLOADER_MIDDLEWARES: dict[str, int | None] = {
        "scrapy.downloadermiddlewares.offsite.OffsiteMiddleware": None,
    }

    EXTENSIONS: dict[str, int] = {
        "src.companies_website.storage.csv_persistence.CsvPersistenceExtension": 300,
    }

    # --- Settings Playwright ---
    PLAYWRIGHT_BROWSER_TYPE: str = "chromium"
    PLAYWRIGHT_PROCESS_REQUEST_HEADERS: Any | None = None
    PLAYWRIGHT_LAUNCH_OPTIONS: dict[str, Any] = {
        "headless": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    }
    PLAYWRIGHT_CONTEXTS: dict[str, Any] = {
        "default": {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080},
            "locale": "ru-RU",
            "timezone_id": "Europe/Moscow",
        }
    }

    # --- Other settings ---
    ROBOTSTXT_OBEY: bool = False
    RETRY_TIMES: int = 3
    RETRY_HTTP_CODES: list[int] = [403, 502, 503, 504, 408, 429]
    HTTPERROR_ALLOWED_CODES: list[int] = [403, 405]
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    COOKIES_ENABLED: bool = False
    REDIRECT_MAX_TIMES: int = 4
    DNS_TIMEOUT: int = 10
    MEMUSAGE_ENABLED: bool = True
    MEMUSAGE_LIMIT_MB: int = 512
    CLOSESPIDER_TIMEOUT: int = 3600
    CLOSESPIDER_ERRORCOUNT: int = 50

    DEFAULT_REQUEST_HEADERS: dict[str, str] = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://google.com",
    }

    AUTOTHROTTLE_ENABLED: bool = True
    AUTOTHROTTLE_START_DELAY: float = 0.5
    AUTOTHROTTLE_MAX_DELAY: float = 5.0
    AUTOTHROTTLE_TARGET_CONCURRENCY: float = 2.0
