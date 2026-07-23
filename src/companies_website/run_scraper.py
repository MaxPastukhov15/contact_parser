"""Standalone Scrapy runner for CompanyWebsiteSpider.

This is an alternative entry point for running the spider directly
(via ``python run_scraper.py``) without the unified CLI. For normal
usage prefer ``terra-dok run-scraper`` instead.

Configures Scrapy with Playwright download handler, curl-cffi
middleware for anti-bot bypass, and CsvPersistenceExtension for
incremental saves.
"""

import asyncio
import logging
import sys
from pathlib import Path


def main() -> None:
    """Launch CompanyWebsiteSpider via Scrapy CrawlerProcess."""
    log = logging.getLogger("run_scraper")

    import twisted.internet.asyncioreactor

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    twisted.internet.asyncioreactor.install()

    from scrapy.crawler import CrawlerProcess
    from scrapy.settings import Settings

    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.companies_website.core.website_scraper import CompanyWebsiteSpider
    from src.configs.settings import config

    scrapy_settings = Settings()
    scrapy_custom_dict = config.scrapy.model_dump()
    for key, value in scrapy_custom_dict.items():
        scrapy_settings.set(key, str(value) if isinstance(value, Path) else value)

    scrapy_settings.set(
        "TWISTED_REACTOR",
        "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    )
    scrapy_settings.set(
        "DOWNLOADER_MIDDLEWARES",
        {
            "scrapy.downloadermiddlewares.offsite.OffsiteMiddleware": None,
            "scrapy_curl_cffi.middlewares.CurlCffiMiddleware": 200,
        },
    )
    scrapy_settings.set(
        "EXTENSIONS",
        {
            "src.companies_website.storage.csv_persistence.CsvPersistenceExtension": 300,
        },
    )
    scrapy_settings.set(
        "DOWNLOAD_HANDLERS",
        {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
    )
    scrapy_settings.set("CURL_CFFI_OPTIONS", {"impersonate": "chrome120"})

    csv_path = "C:/dev/parser/contact_parser/maps_data/contacts/final_2gis.csv"

    process = CrawlerProcess(scrapy_settings)
    crawler = process.create_crawler(CompanyWebsiteSpider)
    process.crawl(crawler, file_path=csv_path)

    try:
        log.info("[RUN] Calling process.start()...")
        process.start()
        log.info("[RUN] process.start() returned normally!")
    except KeyboardInterrupt:
        log.info("[RUN] KeyboardInterrupt caught.")
    else:
        log.info("[RUN] Done.")


if __name__ == "__main__":
    main()
