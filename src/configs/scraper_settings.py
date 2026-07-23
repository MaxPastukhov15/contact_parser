from pydantic import BaseModel
from pathlib import Path
from dataclasses import dataclass

@dataclass
class DataPaths:
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    REGIONS_PATH: Path = BASE_DIR / "maps_data" / "regions.csv"
    RUBRICS_PATH: Path =  BASE_DIR / "maps_data" / "rubrics.json"
    ENV_PATH: Path = BASE_DIR / ".env"

class ScrapySettings(BaseModel):
    DOWNLOAD_DELAY: float = 0.5
    DOWNLOAD_MAXSIZE: int = 2_000_000
    CONCURRENT_REQUESTS: int = 8
    CONCURRENT_REQUESTS_PER_DOMAIN: int = 2
    CONTACTS_CSV_PATH: Path = DataPaths.BASE_DIR / "maps_data" / "contacts" / "final_2gis.csv"
    DOWNLOAD_TIMEOUT: int = 15

    ROBOTSTXT_OBEY: bool = False
    RETRY_TIMES: int = 2
    RETRY_HTTP_CODES: list[int] = [403, 502, 503, 504, 408, 429]
    HTTPERROR_ALLOWED_CODES: list[int] = [403, 405]
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    COOKIES_ENABLED: bool = False
    REDIRECT_MAX_TIMES: int = 4
    DNS_TIMEOUT: int = 10
    MEMUSAGE_ENABLED: bool = True
    MEMUSAGE_LIMIT_MB: int = 512
    CLOSESPIDER_TIMEOUT: int = 3600
    CLOSESPIDER_ERRORCOUNT: int = 50

    AUTOTHROTTLE_ENABLED: bool = True
    AUTOTHROTTLE_START_DELAY: float = 0.5
    AUTOTHROTTLE_MAX_DELAY: float = 5.0
    AUTOTHROTTLE_TARGET_CONCURRENCY: float = 2.0
