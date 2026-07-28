import random
from urllib.parse import urlparse

import polars as pl
import scrapy
from scrapy import signals
from twisted.internet import reactor

from src.companies_website.discovery import (
    ContactPageFinder,
    classify_error,
    classify_response,
)
from src.companies_website.extractors import FIELD_EXTRACTORS, FIELDS
from src.companies_website.utils import MSG
from src.companies_website.utils.stats import ScrapeStats
from src.configs.contacts_config import ContactsFinderSettings


class CompanyWebsiteSpider(scrapy.Spider):
    name = "company_website_parser"

    def __init__(self, file_path: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_path = file_path
        self.stats = ScrapeStats(self.logger)
        self._finder = ContactPageFinder(self.logger)

    async def start(self):
        initial_df = pl.read_csv(self.file_path)
        filtered_df = initial_df.filter(
            pl.col("Адрес сайта").is_not_null()
            & (
                pl.col("Чем занимается").is_null()
                | pl.col("Адрес офиса").is_null()
                | pl.col("Номер телефона").is_null()
                | pl.col("Электронный адрес").is_null()
            )
        )
        self.logger.info(MSG.found_records(filtered_df.height))

        for row in filtered_df.iter_rows(named=True):
            url = row["Адрес сайта"].strip()
            if not url or not isinstance(url, str):
                continue
            if not url.startswith("http"):
                url = "https://" + url

            domain = urlparse(url).netloc.replace("www.", "")

            if domain in ContactsFinderSettings.BLOCKED_DOMAINS:
                self.logger.debug(MSG.blocked(domain, url))
                continue

            self.stats.items_yielded += 1
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={"csv_data": row, "domain": domain},
                errback=self.handle_error,
                dont_filter=True,
            )

        self.logger.info(MSG.yield_done(self.stats.items_yielded))

    def _fill_fields(self, response, csv_data: dict) -> tuple[dict, str, int, int]:
        updated_row = dict(csv_data)

        try:
            html_text = response.text
        except AttributeError:
            html_text = ""

        before = sum(1 for k in FIELDS if updated_row.get(k))

        for field, extractor in FIELD_EXTRACTORS.items():
            if not updated_row.get(field):
                updated_row[field] = extractor(response, html_text, self.logger)

        after = sum(1 for k in FIELDS if updated_row.get(k))
        return updated_row, html_text, before, after

    def _crawl_request(self, request):
        self.crawler.engine.crawl(request)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def parse(self, response):
        csv_data = response.meta["csv_data"]
        url = csv_data.get("Адрес сайта", response.url)

        if response.status != 200:
            if response.meta.get("is_contacts_page"):
                self.stats.contact_page_skipped += 1
                self.logger.debug(MSG.contact_page_skip(response.status, url))
                yield dict(csv_data)
            else:
                yield from self.stats.record_skip(dict(csv_data), url, f"HTTP {response.status}")
            return

        html_text = response.text if hasattr(response, "text") else ""

        reason = classify_response(response, html_text)
        if reason:
            yield from self.stats.record_skip(dict(csv_data), url, reason)
            return

        if response.meta.get("is_contacts_page"):
            yield from self._parse_contact_page(response)
            return

        updated_row, html_text, before, after = self._fill_fields(response, csv_data)
        new_fields = after - before
        self.stats.fields_filled += new_fields

        missing = [k for k in FIELDS if not updated_row.get(k)]
        if not missing:
            yield from self.stats.record_success(updated_row, url, html_text, new_fields, after)
            return

        current_path = urlparse(response.url).path.rstrip("/")
        contact_pages = self._finder.find_pages(response, current_path)

        if not contact_pages:
            yield from self.stats.record_success(updated_row, url, html_text, new_fields, after)
            return

        self.logger.debug(MSG.contacts(len(contact_pages), contact_pages))
        for i, contact_url in enumerate(contact_pages):
            self.stats.items_yielded += 1
            yield scrapy.Request(
                url=contact_url,
                callback=self.parse,
                meta={
                    "csv_data": updated_row,
                    "domain": response.meta["domain"],
                    "is_contacts_page": True,
                    "parent_url": url,
                    "contact_index": i + 1,
                    "total_contacts": len(contact_pages),
                },
                errback=self.handle_error,
                dont_filter=True,
            )

    def _parse_contact_page(self, response):
        csv_data = response.meta["csv_data"]
        parent_url = response.meta.get("parent_url", csv_data.get("Адрес сайта", response.url))
        contact_index = response.meta.get("contact_index", 1)
        total_contacts = response.meta.get("total_contacts", 1)

        updated_row, html_text, before, after = self._fill_fields(response, csv_data)
        new_fields = after - before
        self.stats.fields_filled += new_fields
        if contact_index == total_contacts:
            self.stats.flag_if_suspected_spa(html_text, parent_url, after, len(FIELDS))

        tag = f"+contacts({contact_index}/{total_contacts}) "
        yield from self.stats.record_success(
            updated_row, parent_url, html_text, new_fields, after, tag=tag
        )

    def handle_error(self, failure):
        csv_data = failure.request.meta.get("csv_data")
        if csv_data:
            url = csv_data.get("Адрес сайта", failure.request.url)
            response = getattr(failure.value, "response", None)
            status = getattr(response, "status", None)

            if failure.request.meta.get("is_contacts_page"):
                self.stats.contact_page_skipped += 1
                self.logger.debug(MSG.contact_page_skip(status, url))
                self.crawler.signals.send_catch_log(
                    signal=signals.item_scraped,
                    item=dict(csv_data),
                    response=None,
                    spider=self,
                )
                return

            body = response.text if response is not None and hasattr(response, "text") else ""
            reason, retry = classify_error(
                status,
                body,
                failure.request.meta.get("playwright_retry", False),
            )

            if reason:
                yield from self.stats.record_skip(dict(csv_data), url, reason)
                return

            if retry:
                self.logger.info(MSG.retry_pw(url, status))
                request = scrapy.Request(
                    url=failure.request.url,
                    callback=self.parse,
                    meta={**failure.request.meta, "playwright": True, "playwright_retry": True},
                    errback=self.handle_error,
                    dont_filter=True,
                )
                reactor.callLater(random.uniform(0.5, 1.5), self._crawl_request, request)
                return

            self.stats.record_error(url, status, failure.getErrorMessage())
            self.crawler.signals.send_catch_log(
                signal=signals.item_scraped,
                item=dict(csv_data),
                response=None,
                spider=self,
            )
            self.stats.check_too_many_errors()
