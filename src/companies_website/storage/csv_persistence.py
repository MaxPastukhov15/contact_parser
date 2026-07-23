import atexit
import time

from scrapy import signals
from twisted.internet import reactor

from src.companies_website.storage.csv_uow import CSVUnitOfWork
from src.companies_website.utils.log_lifecycle import log_lifecycle


class CsvPersistenceExtension:
    """Владеет всем жизненным циклом сохранения результатов парсинга:
      - слушает item_scraped и request_scheduled, чтобы знать прогресс,
        не требуя от спайдера вести собственные счётчики для этого;
      - буферизует item'ы и периодически чекпоинтит их в CSVUnitOfWork;
      - следит за "залипанием" (watchdog) и форсирует сохранение/закрытие,
        если прогресса нет слишком долго;
      - делает финальный save+dedup на spider_closed;
      - регистрирует atexit-страховку на случай, если процесс убьют мимо
        штатного scrapy shutdown.

    Спайдеру достаточно:
      1) хранить путь к файлу в self.file_path;
      2) yield'ить готовые dict-строки как items вместо накопления в списке.

    Подключается через настройку EXTENSIONS (см. run_scraper.py).
    """

    CHECKPOINT_INTERVAL_SETTING = "CSV_CHECKPOINT_INTERVAL"
    DEFAULT_CHECKPOINT_INTERVAL = 50
    STALL_WARNING_SECONDS = 60
    STALL_FORCE_CLOSE_SECONDS = 300
    WATCHDOG_POLL_SECONDS = 30

    def __init__(self, crawler):
        self.crawler = crawler
        self.checkpoint_interval = crawler.settings.getint(
            self.CHECKPOINT_INTERVAL_SETTING, self.DEFAULT_CHECKPOINT_INTERVAL
        )

        self.repo: CSVUnitOfWork | None = None
        self.logger = None
        self._spider = None

        self.buffer: list[dict] = []
        self.requests_yielded = 0
        self.items_done = 0

        self.checkpoint_in_progress = False
        self.spider_closing = False
        self.last_progress_time = time.time()
        self._watchdog_call = None
        self._atexit_registered = False

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls(crawler)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(ext.request_scheduled, signal=signals.request_scheduled)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    # ------------------------------------------------------------------
    # Сигналы
    # ------------------------------------------------------------------

    def spider_opened(self, spider):
        file_path = getattr(spider, "file_path", None)
        self.repo = CSVUnitOfWork(file_path, spider.logger)
        self.logger = spider.logger
        self._spider = spider

        self._register_atexit_safety_net()
        self._watchdog_call = reactor.callLater(self.WATCHDOG_POLL_SECONDS, self._watchdog)
        self.logger.info("[PERSISTENCE] Расширение готово, watchdog запланирован через 30с.")

    def request_scheduled(self, _request, _spider):
        self.requests_yielded += 1

    def item_scraped(self, item, _response, _spider):
        self.buffer.append(dict(item))
        self.items_done += 1
        self.last_progress_time = time.time()

        if self.items_done % self.checkpoint_interval == 0:
            self._checkpoint()

    def spider_closed(self, _spider, _reason):
        self._cancel_watchdog()
        self._finalize()

    # ------------------------------------------------------------------
    # Сохранение
    # ------------------------------------------------------------------

    def _checkpoint(self):
        self.checkpoint_in_progress = self.repo.save_checkpoint(
            self.buffer, self.checkpoint_in_progress
        )

    def _finalize(self):
        if self.spider_closing:
            return
        flags = self.repo.save_final(
            self.buffer, self.checkpoint_in_progress, self.spider_closing, self._watchdog_call
        )
        if flags:
            self.checkpoint_in_progress, self.spider_closing = flags

    # ------------------------------------------------------------------
    # Watchdog
    # ------------------------------------------------------------------

    def _cancel_watchdog(self):
        if self._watchdog_call and self._watchdog_call.active():
            self._watchdog_call.cancel()
        self._watchdog_call = None

    @log_lifecycle()
    def _watchdog(self):
        if self.spider_closing:
            return

        elapsed = time.time() - self.last_progress_time
        pending = self.requests_yielded - self.items_done

        if pending <= 0 and not self.checkpoint_in_progress:
            self.logger.info("[WATCHDOG] Все запросы обработаны.")
            self._finalize()
            return

        if elapsed > self.STALL_FORCE_CLOSE_SECONDS:
            self.logger.warning(
                f"[WATCHDOG] Нет прогресса {elapsed:.0f}с — "
                f"обработано {self.items_done}/{self.requests_yielded}, принудительное закрытие"
            )
            self._finalize()
            # NB: если на вашей версии Scrapy `crawler.close_spider` отсутствует,
            # замените на `self.crawler.engine.close_spider(self._spider, reason=...)`.
            self.crawler.close_spider(self._spider, reason="watchdog_timeout")
            return

        if elapsed > self.STALL_WARNING_SECONDS:
            self.logger.warning(
                f"[WATCHDOG] Нет прогресса {elapsed:.0f}с — "
                f"обработано {self.items_done}/{self.requests_yielded}"
            )
            self._checkpoint()

        self._watchdog_call = reactor.callLater(self.WATCHDOG_POLL_SECONDS, self._watchdog)

    # ------------------------------------------------------------------
    # Страховка на случай жёсткого завершения процесса
    # ------------------------------------------------------------------

    def _register_atexit_safety_net(self):
        if self._atexit_registered:
            return
        self._atexit_registered = True

        def _emergency_save():
            if self.spider_closing or not self.buffer:
                self.logger.info("[EXIT] Нечего сохранять аварийно.")
                return
            self.logger.info(f"[EXIT] Emergency save: {len(self.buffer)} результатов")
            snapshot = list(self.buffer)
            self.buffer.clear()
            self.repo.commit(snapshot, "EXIT")

        atexit.register(_emergency_save)
