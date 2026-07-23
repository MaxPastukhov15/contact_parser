from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from src.configs.scraper_settings import DataPaths, ScrapySettings


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DataPaths.ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    TWO_GIS_API_KEY: str = Field(default="", description="API KEY 2GIS")

    HEADLESS_BROWSER: bool = Field(default=False, description="Запуск браузера в скрытом режиме")
    PAGE_TIMEOUT_MS: int = Field(default=30000, description="Таймаут ожидания элементов в мс")

    MAX_PAGES_PER_QUERY: int = Field(default=5, description="Сколько страниц выдачи листать для одного запроса")

    SQLITE_DB_PATH: str = Field(default="terra_doc_leads.db", description="Путь к БД SQLite")
    OUTPUT_DIR: Path = Field(default=Path("output"), description="Папка для CSV выгрузок")
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования приложения")

    AUTH_TOKEN_MAX_AGE_HOURS: int = Field(default=6, description="Время жизни кук 2ГИС")

    scrapy: ScrapySettings = Field(default_factory=ScrapySettings)

config = AppSettings()
