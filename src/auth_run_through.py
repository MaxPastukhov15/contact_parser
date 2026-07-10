import json
import logging
import sqlite3
import time

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC  # noqa: N812
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SessionAuthManager:
    """Session & Auth Manager for 2GIS and Yandex Maps.

    Единственная задача — раз в несколько часов генерировать «ключи от двери».
    Запускает undetected-chromedriver, заходит на главные страницы 2ГИС,
    перехватывает сессионные куки и внутренние токены, сохраняет в SQLite.
    """

    def __init__(self, db_path: str = "terra_doc_leads.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    service TEXT PRIMARY KEY,
                    cookies TEXT,
                    headers TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_state (
                    service TEXT PRIMARY KEY,
                    data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    #  2GIS
    # ------------------------------------------------------------------

    CHROME_VERSION: int = 137  # укажите вашу версию Chrome (chrome://settings/help)

    def refresh_2gis(self, headless: bool = True) -> list[dict]:
        """Open 2GIS in undetected-chromedriver, save session cookies + headers.

        Returns:
            List of cookie dicts.
        """
        driver = uc.Chrome(headless=headless, version_main=self.CHROME_VERSION)
        try:
            logger.info("Navigating to 2GIS search page …")
            driver.get("https://2gis.ru/spb/search/строительство")
            time.sleep(4)

            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/firm/']"))
            )

            cookies = driver.get_cookies()
            logger.info("Got %d cookies from 2GIS", len(cookies))

            user_agent = driver.execute_script("return navigator.userAgent")

            headers = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/json,*/*",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Referer": "https://2gis.ru/",
            }

            self._save_tokens("2gis", cookies, headers)
            return cookies

        except Exception:
            logger.exception("Failed to refresh 2GIS session")
            return []
        finally:
            driver.quit()

    # ------------------------------------------------------------------
    #  Supl.biz
    # ------------------------------------------------------------------

    def refresh_supl_biz(self, headless: bool = False) -> list[dict]:
        """Open supl.biz, wait for user login, save cookies.

        headless=False так как нужно вручную войти в аккаунт.
        После логина страница сама перенаправит на главную — ждём
        появления элемента, которого нет на странице логина.
        """
        driver = uc.Chrome(headless=headless, version_main=self.CHROME_VERSION)
        try:
            logger.info("Navigating to supl.biz login …")
            driver.get("https://supl.biz/login")
            time.sleep(2)

            logger.info(
                "Ожидание входа в аккаунт supl.biz… "
                "Войдите в браузере вручную."
            )
            # Ждём пока кука jwtauth появится (максимум 5 мин)
            WebDriverWait(driver, 300).until(
                lambda d: any(
                    c["name"] == "jwtauth" for c in d.get_cookies()
                )
            )
            time.sleep(2)

            cookies = driver.get_cookies()
            logger.info("Got %d cookies from supl.biz", len(cookies))

            user_agent = driver.execute_script("return navigator.userAgent")
            headers = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/json,*/*",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }

            self._save_tokens("supl_biz", cookies, headers)
            return cookies

        except Exception:
            logger.exception("Failed to refresh supl.biz session")
            return []
        finally:
            driver.quit()

    # ------------------------------------------------------------------
    #  Yandex Maps
    # ------------------------------------------------------------------

    def refresh_yandex(self, headless: bool = True) -> list[dict]:
        """Open Yandex Maps, save session cookies."""
        driver = uc.Chrome(headless=headless, version_main=self.CHROME_VERSION)
        try:
            logger.info("Navigating to Yandex Maps …")
            driver.get("https://yandex.ru/maps")
            time.sleep(4)

            cookies = driver.get_cookies()
            logger.info("Got %d cookies from Yandex", len(cookies))
            self._save_tokens("yandex", cookies)
            return cookies
        except Exception:
            logger.exception("Failed to refresh Yandex session")
            return []
        finally:
            driver.quit()

    # ------------------------------------------------------------------
    #  Storage helpers
    # ------------------------------------------------------------------

    def _save_tokens(
        self,
        service: str,
        cookies: list[dict],
        headers: dict | None = None,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO auth_tokens (service, cookies, headers, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (service, json.dumps(cookies), json.dumps(headers) if headers else None),
            )
            conn.commit()

    def get_cookies(self, service: str = "2gis") -> list[dict]:
        """Read stored cookies for *service*."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT cookies FROM auth_tokens WHERE service = ?", (service,)
            ).fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return []

    def get_headers(self, service: str = "2gis") -> dict:
        """Read stored headers for *service*."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT headers FROM auth_tokens WHERE service = ?", (service,)
            ).fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return {}

    def save_auth_state(self, service: str, data: dict) -> None:
        """Save arbitrary auth state dict."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO auth_state (service, data, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (service, json.dumps(data)),
            )
            conn.commit()

    def get_auth_state(self, service: str) -> dict | None:
        """Read stored auth state."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data FROM auth_state WHERE service = ?", (service,)
            ).fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return None

    def is_token_valid(self, service: str, max_age_hours: int = 6) -> bool:
        """Check if a stored token is still fresh."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT updated_at FROM auth_tokens WHERE service = ?
                """,
                (service,),
            ).fetchone()
        if not row:
            return False

        updated = datetime.fromisoformat(row[0])
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - updated
        return delta.total_seconds() < max_age_hours * 3600
