from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.configs.scraper_settings import DataPaths, ScrapySettings


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DataPaths.ENV_PATH, env_file_encoding="utf-8", extra="ignore"
    )

    TWO_GIS_API_KEY: str = Field(default="", description="API KEY 2GIS")

    HEADLESS_BROWSER: bool = Field(default=False, description="Запуск браузера в скрытом режиме")
    PAGE_TIMEOUT_MS: int = Field(default=30000, description="Таймаут ожидания элементов в мс")

    MAX_PAGES_PER_QUERY: int = Field(
        default=5, description="Сколько страниц выдачи листать для одного запроса"
    )

    OUTPUT_DIR: Path = Field(default=Path("output"), description="Папка для CSV выгрузок")
    LOG_LEVEL: str = Field(default="DEBUG", description="Уровень логирования приложения")

    scrapy: ScrapySettings = Field(default_factory=ScrapySettings)


config = AppSettings()
