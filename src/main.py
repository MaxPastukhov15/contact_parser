import os
import sys
import logging
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from contact_parser.src.auth_run_through import SessionAuthManager
from src.parsers.maps_spider import TwoGisAPIParser
from src.parsers.archi_spider import ArchiSpider
from src.parsers.b2b_catalog_spider import B2BCatalogSpider
from contact_parser.src.configs import settings as project_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("terra_doc.main")

def run_pipeline():
    logger.info("=== Запуск парсинга лидов для ТЕРРА ДОК ===")

    # Этап 1: Авторизация и обновление сессии 2ГИС
    logger.info("Этап 1: Проверка и обновление сессионных токенов 2ГИС...")
    try:
        auth_manager = SessionAuthManager(db_path=project_settings.SQLITE_DB_PATH)
        
        # Запускаем обновление сессии. 
        # headless=True означает, что Chrome откроется скрытно в бэкграунде.
        # Если нужно отладить или посмотреть, что происходит — поставьте headless=False.
        auth_manager.refresh_2gis(headless=True)
        logger.info("Сессия 2ГИС успешно обновлена и сохранена в БД.")
    except Exception as e:
        logger.error(f"Критическая ошибка при обновлении сессии 2ГИС: {e}")
        logger.warning("Попытка продолжить запуск Scrapy (возможно, старые токены еще активны)...")

    # Этап 1.5: Авторизация Supl.biz (если нет свежих кук)
    logger.info("Этап 1.5: Проверка сессии Supl.biz...")
    try:
        if not auth_manager.is_token_valid("supl_biz", max_age_hours=12):
            logger.info("Нет свежих кук Supl.biz — запускаю Selenium для входа...")
            auth_manager.refresh_supl_biz(headless=False)
        else:
            logger.info("Куки Supl.biz валидны.")
    except Exception as e:
        logger.error(f"Ошибка при авторизации Supl.biz: {e}")
        logger.warning("Продолжаю без кук Supl.biz (возможно, не все заказы будут доступны).")

    # Этап 2: Запуск Scrapy паука
    logger.info("Этап 2: Инициализация и запуск Scrapy паука...")
    
    # Загружаем конфигурацию из нашего src/settings.py
    scrapy_settings = Settings()
    scrapy_settings.setmodule(project_settings)
    
    # Создаем процесс и регистрируем в нем наших пауков
    process = CrawlerProcess(scrapy_settings)
    process.crawl(MapsSpider)
    process.crawl(ArchiSpider)
    process.crawl(B2BCatalogSpider)

    logger.info("Пауки 'maps', 'archi' и 'b2b_catalog' успешно запущены. Сбор данных начался.")
    # Скрипт заблокируется на этой строчке, пока Scrapy полностью не отработает
    process.start() 
    
    logger.info("=== Парсинг успешно завершен! ===")
    logger.info(f"Сырые данные сохранены в SQLite: {project_settings.SQLITE_DB_PATH}")
    logger.info("Готовая CSV выгрузка сформирована в папке output/")

if __name__ == "__main__":
    run_pipeline()