import threading

import polars as pl
from twisted.internet import threads

from src.companies_website.utils import log_lifecycle, MSG


class CSVUnitOfWork:
    """Единая точка правды для CSV-файла результатов.

    Причины, по которым это отдельный класс, а не набор функций в спайдере:
      - Раньше `initial_df` читался один раз при старте и больше не обновлялся,
        а `_dedup_csv` дедуплицировал файл именно по этому устаревшему снапшоту —
        то есть каждый финальный save стирал все чекпоинты, записанные за время
        работы паука. Здесь `self.df` — единственный источник правды, который
        обновляется при каждом commit.
      - Раньше `threading.Lock()` создавался заново на каждый вызов `add()` —
        это no-op, никакой взаимоисключающей блокировки не было. Здесь лок
        живёт как атрибут инстанса.
    """

    def __init__(self, file_path: str | None, logger) -> None:
        if file_path is None:
            raise ValueError("Need to specify the path")

        self.csv_path = file_path
        self.logger = logger
        self._lock = threading.Lock()
        self.df = pl.read_csv(self.csv_path)

    def get(self) -> pl.DataFrame:
        return self.df

    def commit(self, results: list[dict], tag: str) -> None:
        """Мержит новые результаты в self.df, дедуплицирует по 'Адрес сайта'
        (оставляя последнюю запись) и перезаписывает файл целиком.
        Дедуп и запись происходят под одним локом, чтобы конкурентные
        коммиты (checkpoint из потока + final из реактора) не гонялись
        друг с другом за файл.
        """
        if not results:
            return

        with self._lock:
            new_df = pl.DataFrame(results)
            merged = pl.concat([self.df, new_df], how="diagonal")
            before = merged.height
            fill_cols = ["Чем занимается", "Адрес офиса", "Номер телефона", "Электронный адрес"]
            merged = merged.with_columns(
                pl.sum_horizontal([pl.col(c).is_not_null() for c in fill_cols]).alias("_fill_score")
            ).sort("_fill_score")

            self.df = merged.unique(subset=["Адрес сайта"], keep="last").drop("_fill_score")
            removed = before - self.df.height

            self.df.write_csv(self.csv_path)
            self.logger.info(MSG.written(tag, new_df.height, removed, self.df.height))

    @log_lifecycle()
    def save_checkpoint(self, scraped_results: list, checkpoint_in_progress: bool) -> bool:
        """Возвращает актуальное состояние checkpoint_in_progress.
        Раньше при checkpoint_in_progress=True функция ничего не возвращала
        (implicit None), и вызывающий код делал bool(None) == False —
        то есть флаг "чекпоинт идёт" сбрасывался, даже если чекпоинт
        всё ещё выполнялся в фоновом потоке. Теперь при активном
        чекпоинте флаг сохраняется как есть.
        """
        if checkpoint_in_progress:
            return True

        if not scraped_results:
            return False

        snapshot = list(scraped_results)
        scraped_results.clear()

        d = threads.deferToThread(self.commit, snapshot, "CHECKPOINT")
        d.addErrback(lambda f: self.logger.error(f"CHECKPOINT err: {f.getErrorMessage()}"))

        return True

    @log_lifecycle()
    def save_final(
        self,
        scraped_results: list,
        checkpoint_in_progress: bool,
        spider_closing: bool,
        watchdog_delayed,
    ) -> tuple[bool, bool] | None:

        self.logger.info(
            MSG.final_state(len(scraped_results), spider_closing, checkpoint_in_progress)
        )
        if spider_closing:
            return None

        spider_closing = True

        if watchdog_delayed and watchdog_delayed.active():
            watchdog_delayed.cancel()

        if scraped_results:
            snapshot = list(scraped_results)
            scraped_results.clear()
            self.commit(snapshot, "FINAL")

        return checkpoint_in_progress, spider_closing
