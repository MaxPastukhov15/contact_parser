"""Scrapy spider command handler.

Launches ``CompanyWebsiteSpider`` which visits company websites listed
in a contacts CSV, extracts additional contact information (phones,
emails, addresses) and writes enriched results back to CSV.

Uses Scrapy with Playwright download handler and curl-cffi middleware
for anti-bot bypass.
"""
import asyncio
import sys
from pathlib import Path


def run_scraper_cmd(args):
    """Run the CompanyWebsiteSpider Scrapy crawler.

    Args:
        args: Parsed argparse namespace from ``terra-dok run-scraper``.
    """
    project_root = Path(__file__).resolve().parents[2]
    csv_path = args.file or str(project_root / "maps_data" / "contacts" / "final_2gis.csv")

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    print(f"[SCRAPER] Starting CompanyWebsiteSpider, CSV: {csv_path}")

    import twisted.internet.asyncioreactor
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    twisted.internet.asyncioreactor.install()

    from scrapy.crawler import CrawlerProcess
    from scrapy.settings import Settings
    from src.configs.settings import config
    from src.companies_website.core.website_scraper import CompanyWebsiteSpider

    scrapy_settings = Settings()
    for key, value in config.scrapy.model_dump().items():
        if isinstance(value, Path):
            value = str(value)
        scrapy_settings.set(key, value)

    scrapy_settings.set(
        "TWISTED_REACTOR",
        "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    )
    scrapy_settings.set("DOWNLOADER_MIDDLEWARES", {
        "scrapy.downloadermiddlewares.offsite.OffsiteMiddleware": None,
        "scrapy_curl_cffi.middlewares.CurlCffiMiddleware": 200,
    })
    scrapy_settings.set("EXTENSIONS", {
        "src.companies_website.storage.csv_persistence.CsvPersistenceExtension": 300,
    })
    scrapy_settings.set("DOWNLOAD_HANDLERS", {
        "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    })
    scrapy_settings.set("CURL_CFFI_OPTIONS", {"impersonate": "chrome120"})

    process = CrawlerProcess(scrapy_settings)
    crawler = process.create_crawler(CompanyWebsiteSpider)
    process.crawl(crawler, file_path=csv_path)

    try:
        process.start()
    except KeyboardInterrupt:
        print("[SCRAPER] Stopped by user.")

    print("[SCRAPER] Done.")
