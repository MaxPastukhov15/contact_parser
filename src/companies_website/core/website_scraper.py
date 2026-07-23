import polars as pl
import scrapy

from urllib.parse import urlparse
from scrapy import signals
from scrapy.exceptions import CloseSpider
from src.companies_website.extractors import (extract_description, 
            extract_address, extract_phone, extract_email)
from src.companies_website.discovery import ContactPageFinder, looks_js_rendered
from src.configs.contacts_config import ContactsFinderSettings

FIELDS = ("Чем занимается", "Адрес офиса", "Номер телефона", "Электронный адрес")
FIELD_EXTRACTORS = {
    "Чем занимается": lambda resp, text, log: extract_description(resp, log),
    "Адрес офиса": lambda resp, text, log: extract_address(text, log),
    "Номер телефона": lambda resp, text, log: extract_phone(text, log),
    "Электронный адрес": lambda resp, text, log: extract_email(resp, text, log),
}


class CompanyWebsiteSpider(scrapy.Spider):
    name = "company_website_parser"

    def __init__(self, file_path: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_path = file_path

        self._parse_ok = 0
        self._parse_error = 0
        self._fields_filled = 0
        self._consecutive_errors = 0
        self._items_yielded = 0
        self._suspected_spa = 0

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
        self.logger.info(
            f"Found {filtered_df.height} records for updates"
        )

        for row in filtered_df.iter_rows(named=True):
            url = row["Адрес сайта"].strip()
            if not url or not isinstance(url, str):
                continue
            if not url.startswith("http"):
                url = "https://" + url

            domain = urlparse(url).netloc.replace("www.", "")

            if domain in ContactsFinderSettings.BLOCKED_DOMAINS:
                self.logger.debug(f"[SKIP] Заблокирован: {domain} — {url}")
                continue

            self._items_yielded += 1
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={"csv_data": row, "domain": domain},
                errback=self.handle_error,
                dont_filter=True,
            )

        self.logger.info(f"Yield loop finished. Total yielded: {self._items_yielded}")


    def _fill_fields(self, response, csv_data: dict) -> tuple[dict, str, int, int]:
        updated_row = dict(csv_data)
        html_text = response.text
        before = sum(1 for k in FIELDS if updated_row.get(k))

        for field, extractor in FIELD_EXTRACTORS.items():
            if not updated_row.get(field):
                updated_row[field] = extractor(response, html_text, self.logger)

        after = sum(1 for k in FIELDS if updated_row.get(k))
        return updated_row, html_text, before, after

    def _record_success(self, row: dict, url: str, html_text: str, 
                        new_fields: int, after: int, tag: str = ""):
        self._parse_ok += 1
        self._consecutive_errors = 0
        size_kb = len(html_text) // 1024
        self.logger.info(
            f"[{self._parse_ok + self._parse_error}] "
            f"OK {url} {tag}({size_kb}KB,+{new_fields} полей, итого заполнено {after}/4)"
        )
        self._log_progress()
        yield row

    def _record_skip(self, row: dict, url: str, reason: str):
        self._parse_error += 1
        self.logger.warning(f"{reason} для {url} — пропускаем извлечение данных")
        self._log_progress()
        yield row

    def _flag_if_suspected_spa(self, html_text: str, url: str, after: int):
        if after >= len(FIELDS):
            return
        if looks_js_rendered(html_text):
            self._suspected_spa += 1
            self.logger.info(f"[SPA?] Подозрение на JS-рендеринг: {url}")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def parse(self, response):
        csv_data = response.meta["csv_data"]
        url = csv_data.get("Адрес сайта", response.url)

        if response.status != 200:
            yield from self._record_skip(dict(csv_data), url, f"HTTP {response.status}")
            return

        final_url = response.url.lower()
        if any(p in final_url for p in ContactsFinderSettings.AUTH_URL_PATTERNS):
            yield from self._record_skip(dict(csv_data), url, f"[AUTH] Редирект на страницу авторизации: {response.url}")
            return

        if response.meta.get("is_contacts_page"):
            yield from self._parse_contact_page(response)
            return

        updated_row, html_text, before, after = self._fill_fields(response, csv_data)
        new_fields = after - before
        self._fields_filled += new_fields

        missing = [k for k in FIELDS if not updated_row.get(k)]
        if not missing:
            yield from self._record_success(updated_row, url, html_text, new_fields, after)
            return

        current_path = urlparse(response.url).path.rstrip("/")
        contact_pages = self._finder.find_pages(response, current_path)

        if not contact_pages:
            yield from self._record_success(updated_row, url, html_text, new_fields, after)
            return

        self.logger.debug(
            f"[CONTACTS] {len(contact_pages)} кандидатов: {contact_pages}"
        )
        for i, contact_url in enumerate(contact_pages):
            self._items_yielded += 1
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
        self._fields_filled += new_fields
        if contact_index == total_contacts: 
            self._flag_if_suspected_spa(html_text, parent_url, after)
            

        tag = f"+contacts({contact_index}/{total_contacts}) "
        yield from self._record_success(updated_row, parent_url, html_text, new_fields, after, tag=tag)

    def handle_error(self, failure):
        csv_data = failure.request.meta.get("csv_data")
        if csv_data:
            url = csv_data.get("Адрес сайта", failure.request.url)
            self.logger.warning(
                f"[{self._parse_ok + self._parse_error + 1}] "
                f"ERR {url}: {failure.getErrorMessage()}"
            )
            self._parse_error += 1
            self._consecutive_errors += 1
            self._log_progress()
            self.crawler.signals.send_catch_log(
                signal=signals.item_scraped,
                item=dict(csv_data),
                response=None,
                spider=self,
            )
            if self._consecutive_errors >= 30:
                self.logger.warning(
                    f"[SPIDER] {self._consecutive_errors} ошибок подряд — закрываю"
                )
                raise CloseSpider("too_many_errors")

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def _log_progress(self):
        done = self._parse_ok + self._parse_error
        if done % 10 == 0:
            self.logger.info(
                f"--- Прогресс: {done}/{self._items_yielded} обработано, "
                f"OK={self._parse_ok}, ERR={self._parse_error}, "
                f"заполнено пол={self._fields_filled}, "
                f"suspected_spa={self._suspected_spa} ---"
            )
