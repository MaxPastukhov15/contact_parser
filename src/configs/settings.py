from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    TWO_GIS_API_KEY: str = Field(default="", description="API KEY 2GIS")

    # Настройки Playwright
    HEADLESS_BROWSER: bool = Field(default=False, description="Запуск браузера в скрытом режиме")
    PAGE_TIMEOUT_MS: int = Field(default=30000, description="Таймаут ожидания элементов в мс")
    
    # Лимиты парсинга
    MAX_PAGES_PER_QUERY: int = Field(default=5, description="Сколько страниц выдачи листать для одного запроса")

    # Пути и База данных
    SQLITE_DB_PATH: str = Field(default="terra_doc_leads.db", description="Путь к БД SQLite")
    OUTPUT_DIR: Path = Field(default=Path("output"), description="Папка для CSV выгрузок")

    # Настройки Scrapy (Throttling & Concurrency)
    DOWNLOAD_DELAY: float = Field(default=1.5, description="Задержка между запросами")
    CONCURRENT_REQUESTS: int = Field(default=4, description="Всего одновременных потоков")
    CONCURRENT_REQUESTS_PER_DOMAIN: int = Field(default=2, description="Потоков на домен")
    
    # Логирование
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования приложения")
    
    # Лимиты сессии (в часах)
    AUTH_TOKEN_MAX_AGE_HOURS: int = Field(default=6, description="Время жизни кук 2ГИС")

config = AppSettings()