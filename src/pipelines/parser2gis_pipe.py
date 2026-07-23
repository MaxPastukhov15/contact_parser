"""Contact enrichment pipeline for 2GIS data.

Reads raw CSV files produced by the 2GIS parser, normalizes and merges
company data (names, phones, emails, websites, addresses), deduplicates
records, and writes a final contacts CSV.

Usage::

    Parser2GISPipe(data_dir=Path("maps_data/parsed_2gis")).run()

Or via CLI::

    terra-dok scrape-2gis -u "https://2gis.ru/..." --pipe

Output columns:
    Название компании, Чем занимается, Категория, Рубрика,
    Электронный адрес, Номер телефона, Адрес сайта, Регион, Адрес офиса
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

DATA_DIR = Path(__file__).resolve().parents[2] / "maps_data" / "parsed_2gis"
OUTPUT_DIR = DATA_DIR.parent / "contacts"
OUTPUT_FILE = OUTPUT_DIR / "final_2gis.csv"

OUTPUT_FIELDS = [
    "Название компании",
    "Чем занимается",
    "Категория",
    "Рубрика",
    "Электронный адрес",
    "Номер телефона",
    "Адрес сайта",
    "Регион",
    "Адрес офиса",
]

CATEGORY_KEYWORDS = [
    (["Реставрац"], "Реставрация"),
    (["Архитектур", "Проектировани"], "Архитектура / Проектирование"),
    (["Дизайн"], "Дизайн"),
    (["Строительств"], "Строительство"),
]

PRIORITY_EMAIL_PREFIXES = (
    "info@",
    "sales@",
    "office@",
    "mail@",
    "admin@",
    "hello@",
    "contact@",
)

PHONE_FULL_LENGTH = 11
PHONE_SHORT_LENGTH = 10


class Parser2GISPipe:
    """Fluent-style pipeline that transforms raw 2GIS CSV into contacts.

    Each processing step returns ``self`` so calls can be chained::

        Parser2GISPipe().run()

    Args:
        data_dir:   Directory containing raw 2GIS CSV files.
        output_file: Path to the final merged contacts CSV.

    """

    def __init__(
        self,
        data_dir: Path = DATA_DIR,
        output_file: Path = OUTPUT_FILE,
    ) -> None:
        """Initialize the pipeline with input/output paths."""
        self.data_dir = data_dir
        self.output_file = output_file
        self.initial_df: pl.DataFrame | None = (
            pl.read_csv(self.output_file) if self.output_file.exists() else None
        )
        self._df: pl.DataFrame = pl.DataFrame()

    def load(self) -> Parser2GISPipe:
        """Load all CSV files from data_dir and concatenate them."""
        csv_files = sorted(self.data_dir.glob("*.csv"))
        frames = [
            pl.read_csv(f, encoding="utf-8-sig", truncate_ragged_lines=True, infer_schema_length=0)
            for f in csv_files
        ]
        self._df = pl.concat(frames, how="diagonal")
        return self

    def process_company_name(self) -> Parser2GISPipe:
        """Map ``Наименование`` → ``Название компании``."""
        self._df = self._df.with_columns(
            pl.col("Наименование").alias("Название компании"),
        )
        return self

    def process_description(self) -> Parser2GISPipe:
        """Map ``Описание`` → ``Чем занимается``."""
        self._df = self._df.with_columns(
            pl.col("Описание").alias("Чем занимается"),
        )
        return self

    def process_category(self) -> Parser2GISPipe:
        """Classify first rubric into a high-level category."""

        def _classify(val: str | None) -> str | None:
            if not val:
                return None
            low = val.strip().lower()
            for keywords, category in CATEGORY_KEYWORDS:
                if any(kw.lower() in low for kw in keywords):
                    return category
            return None

        self._df = self._df.with_columns(
            pl.col("Рубрики")
            .str.split(";")
            .list.first()
            .map_elements(_classify, return_dtype=pl.Utf8)
            .alias("Категория"),
        )
        return self

    def process_rubric(self) -> Parser2GISPipe:
        """Map ``Рубрики`` → ``Рубрика``."""
        self._df = self._df.with_columns(
            pl.col("Рубрики").alias("Рубрика"),
        )
        return self

    def process_email(self) -> Parser2GISPipe:
        """Pick the best email from multi-value columns.

        Priority: info@, sales@, office@, mail@, admin@, hello@, contact@.
        Falls back to the first available email.
        """
        email_cols = [
            c
            for c in self._df.columns
            if re.match(r"^E-mail\s*\d*$", c, re.IGNORECASE) or c.lower() == "e-mail"
        ]

        def _pick(row: tuple[str | None, ...]) -> str | None:
            candidates = [str(val).strip() for val in row if val and str(val).strip()]
            if not candidates:
                return None
            for prefix in PRIORITY_EMAIL_PREFIXES:
                for email in candidates:
                    if email.lower().startswith(prefix):
                        return email
            return candidates[0]

        if email_cols:
            self._df = self._df.with_columns(
                pl.struct(email_cols)
                .map_elements(lambda s: _pick(tuple(s.values())), return_dtype=pl.Utf8)
                .alias("Электронный адрес"),
            )
        else:
            self._df = self._df.with_columns(
                pl.lit(None, dtype=pl.Utf8).alias("Электронный адрес"),
            )
        return self

    def process_phone(self) -> Parser2GISPipe:
        """Normalize phone numbers to ``7-xxx-xxx-xx-xx`` format.

        Handles 8-starting (converts to 7), 10-digit (prepends 7),
        and passes through short numbers as-is.
        """
        phone_cols = [c for c in ("Телефон 1", "Телефон 2", "Телефон 3") if c in self._df.columns]

        def _norm(raw: str | None) -> str | None:
            if not raw:
                return None
            digits = re.sub(r"\D", "", raw)
            if not digits:
                return None
            if digits.startswith("8") and len(digits) >= PHONE_FULL_LENGTH:
                digits = "7" + digits[1:]
            elif not digits.startswith("7") and len(digits) == PHONE_SHORT_LENGTH:
                digits = "7" + digits
            if len(digits) < PHONE_SHORT_LENGTH:
                return raw.strip()
            return f"{digits[0]}-{digits[1:4]}-{digits[4:7]}-{digits[7:9]}-{digits[9:11]}"

        if phone_cols:
            self._df = self._df.with_columns(
                pl.coalesce([pl.col(c) for c in phone_cols])
                .map_elements(_norm, return_dtype=pl.Utf8)
                .alias("Номер телефона"),
            )
        else:
            self._df = self._df.with_columns(
                pl.lit(None, dtype=pl.Utf8).alias("Номер телефона"),
            )
        return self

    def process_website(self) -> Parser2GISPipe:
        """Pick the first website URL and prepend ``http://`` if missing."""
        web_cols = [c for c in ("Веб-сайт 1", "Веб-сайт 2", "Веб-сайт 3") if c in self._df.columns]

        def _fix(val: str | None) -> str | None:
            if not val:
                return None
            url = val.strip()
            if not url:
                return None
            if not url.startswith("http"):
                url = "http://" + url
            return url

        if web_cols:
            self._df = self._df.with_columns(
                pl.coalesce([pl.col(c) for c in web_cols])
                .map_elements(_fix, return_dtype=pl.Utf8)
                .alias("Адрес сайта"),
            )
        else:
            self._df = self._df.with_columns(
                pl.lit(None, dtype=pl.Utf8).alias("Адрес сайта"),
            )
        return self

    def process_region(self) -> Parser2GISPipe:
        """Merge ``Город`` and ``Регион`` into a single ``Регион`` field."""

        def _join_region(row: dict[str, str | None]) -> str | None:
            city = (row.get("Город") or "").strip() or None
            region = (row.get("Регион") or "").strip() or None
            if city and region and city not in region:
                return f"{city}, {region}"
            return region or city

        self._df = self._df.with_columns(
            pl.struct(["Город", "Регион"])
            .map_elements(_join_region, return_dtype=pl.Utf8)
            .alias("Регион"),
        )
        return self

    def process_address(self) -> Parser2GISPipe:
        """Join ``Адрес``, ``Город``, ``Район`` into ``Адрес офиса``."""

        def _join_address(row: dict[str, str | None]) -> str | None:
            parts = []
            for key in ("Адрес", "Город", "Район"):
                val = (row.get(key) or "").strip()
                if val:
                    parts.append(val)
            return ", ".join(parts) if parts else None

        self._df = self._df.with_columns(
            pl.struct(["Адрес", "Город", "Район"])
            .map_elements(_join_address, return_dtype=pl.Utf8)
            .alias("Адрес офиса"),
        )
        return self

    def drop_no_contacts(self) -> Parser2GISPipe:
        """Remove rows that have neither email nor website."""
        self._df = self._df.filter(
            pl.col("Электронный адрес").is_not_null() | pl.col("Адрес сайта").is_not_null(),
        )
        return self

    def deduplicate_contacts(self) -> Parser2GISPipe:
        """Remove duplicate rows by email + phone combination."""
        self._df = self._df.unique(
            subset=["Электронный адрес", "Номер телефона"],
            keep="first",
        )
        return self

    def build(self) -> pl.DataFrame:
        """Select only the output columns."""
        return self._df.select(OUTPUT_FIELDS)

    def run(self) -> pl.DataFrame:
        """Execute the full pipeline and write the result CSV.

        Returns:
            The final Polars DataFrame with enriched contacts.

        """
        result = (
            self.load()
            .process_company_name()
            .process_description()
            .process_category()
            .process_rubric()
            .process_email()
            .process_phone()
            .process_website()
            .process_region()
            .process_address()
            .drop_no_contacts()
            .deduplicate_contacts()
            .build()
        )
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        if self.initial_df is not None:
            result = pl.concat([self.initial_df, result], how="diagonal")
        result.write_csv(self.output_file)
        return result


if __name__ == "__main__":
    Parser2GISPipe().run()
