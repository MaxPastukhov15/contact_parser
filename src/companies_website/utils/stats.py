from __future__ import annotations

from scrapy.exceptions import CloseSpider

from src.companies_website.discovery import looks_js_rendered
from src.companies_website.utils.log_templates import MSG


class ScrapeStats:
    def __init__(self, logger):
        self._logger = logger

        self.parse_ok: int = 0
        self.parse_error: int = 0
        self.fields_filled: int = 0
        self.items_yielded: int = 0
        self.suspected_spa: int = 0
        self.contact_page_skipped: int = 0
        self._consecutive_errors: int = 0

    @property
    def total_done(self) -> int:
        return self.parse_ok + self.parse_error

    @property
    def total_done_plus_one(self) -> int:
        return self.parse_ok + self.parse_error + 1

    # -- record methods (generators) ----------------------------------

    def record_success(
        self,
        row: dict,
        url: str,
        html_text: str,
        new_fields: int,
        after: int,
        tag: str = "",
    ):
        self.parse_ok += 1
        self._consecutive_errors = 0
        size_kb = len(html_text) // 1024
        self._logger.info(MSG.ok(self.total_done, url, tag, size_kb, new_fields, after))
        self._log_progress()
        yield row

    def record_skip(self, row: dict, url: str, reason: str):
        self.parse_error += 1
        self._consecutive_errors = 0
        self._logger.info(MSG.skip(reason, url))
        self._log_progress()
        yield row

    def record_error(self, url: str, status: int | None, error_message: str):
        self.parse_error += 1
        self._consecutive_errors += 1
        self._logger.warning(MSG.err(self.total_done_plus_one, url, status, error_message))
        self._log_progress()

    # -- helpers ------------------------------------------------------

    def flag_if_suspected_spa(
        self,
        html_text: str,
        url: str,
        after: int,
        fields_count: int,
    ):
        if after >= fields_count:
            return
        if looks_js_rendered(html_text):
            self.suspected_spa += 1
            self._logger.info(MSG.spa(url))

    def check_too_many_errors(self):
        if self._consecutive_errors >= 30:
            self._logger.warning(MSG.too_many(self._consecutive_errors))
            raise CloseSpider("too_many_errors")

    # -- internal -----------------------------------------------------

    def _log_progress(self):
        if self.total_done % 10 == 0:
            self._logger.info(
                MSG.progress(
                    self.total_done,
                    self.items_yielded,
                    self.parse_ok,
                    self.parse_error,
                    self.fields_filled,
                    self.suspected_spa,
                    self.contact_page_skipped,
                )
            )
