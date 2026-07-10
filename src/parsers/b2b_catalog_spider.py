import json
import logging
import re
import sqlite3
from collections.abc import AsyncGenerator, Generator
from urllib.parse import urljoin

import scrapy
from scrapy.http import Response

from src.items import ContactItem

logger = logging.getLogger(__name__)


class B2BCatalogSpider(scrapy.Spider):
    """Парсер B2B-площадок Supl.biz и Fis.ru для сбора заявок/тендеров
    на деревянные и дерево-алюминиевые окна.

    ────────────────────────────────────────────────────────────
    Архитектура:
      1. Для каждой площадки обходит категории с заявками на
         деревянные / дерево-алюминиевые окна + фасадные работы.
      2. На странице списка заявок проверяет заголовок/аннотацию
         на TARGET_KEYWORDS — первичная фильтрация.
      3. Если есть совпадение → переходит на детальную страницу
         заявки, извлекает полное описание, контакты заказчика.
      4. Вторичная фильтрация по EXCLUDE_KEYWORDS (отсечь ПВХ).
      5. Если контакты неполные — пытается найти профиль компании
         на той же площадке.
      6. На выходе — ContactItem со статусом:
         - "high" если есть маркеры премиума (порталы, реставрация,
           фахверк, коттеджный посёлок, чертежи)
         - "pending" если обычная целевая заявка
    ────────────────────────────────────────────────────────────
    """

    name = "b2b_catalog"
    allowed_domains: list[str] = [
        "supl.biz",
        "fis.ru",
    ]

    custom_settings = {
        "FEEDS": {
            "output/leads_b2b.csv": {
                "format": "csv",
                "encoding": "utf-8-sig",
                "delimiter": ";",
                "fields": [
                    "company_name",
                    "description",
                    "category",
                    "rubric",
                    "email",
                    "phone",
                    "website_url",
                    "region",
                    "address",
                    "source",
                    "crawl_status",
                ],
                "overwrite": True,
            },
        },
        "DOWNLOAD_DELAY": 3.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "ROBOTSTXT_OBEY": False,
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
        },
    }

    # Загружаются из SQLite через _load_supl_cookies()
    SUPL_COOKIES: dict[str, str] = {}

    @classmethod
    def _load_supl_cookies(cls, db_path: str = "terra_doc_leads.db") -> dict[str, str]:
        """Прочитать куки supl.biz из БД (сохранены SessionAuthManager'ом)."""
        try:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT cookies FROM auth_tokens WHERE service = ?",
                    ("supl_biz",),
                ).fetchone()
            if row and row[0]:
                cookies_list: list[dict] = json.loads(row[0])
                return {c["name"]: c["value"] for c in cookies_list}
        except Exception:
            logger.exception("Failed to load supl.biz cookies from DB")
        return {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.SUPL_COOKIES = self._load_supl_cookies()

    # ── Площадки и категории ────────────────────────────────
    PLATFORMS = {
        "supl.biz": {
            "base": "https://supl.biz",
            "categories": [
                # Основная: деревянные окна, регионы: Москва, МО, СПб, ЛО
                "/orders/derevyannyie-okna-rubric8467/?regions=86,999,1149,96&filter_by_supply_city=true"
            ],
            "paginate_query": "&page={page}",
            "listing_selector": "#orderList > div",
            "order_number_selector": "span::text",
        },
        "fis.ru": {
            "base": "https://fis.ru",
            "categories": [
                "/products/okna-derevyannye/",
                "/products/okna-derevo-alyuminievye/",
                "/products/osteklenie/",
                "/products/fasadnye-raboty/",
            ],
            "paginate": "?page={page}",
            "listing_selector": ".catalog-item, .product-item, .item, tr.catalog-item",
            "title_selector": ".item-title a::text, .product-name a::text, h2 a::text, a.catalog-link::text",
            "link_selector": ".item-title a::attr(href), .product-name a::attr(href), h2 a::attr(href), a.catalog-link::attr(href)",
            "desc_selector": ".item-desc::text, .product-desc::text, .description::text, .anons::text",
        },
    }

    # ── Ключевые слова для первичной фильтрации ────────────
    TARGET_KEYWORDS: list[str] = [
        "деревянн",
        "дуб",
        "лиственниц",
        "дерево-алюмин",
        "алюминий-дерево",
        "евроокн",
        "портал",
        "раздвижн",
        "hs-портал",
        "фахверк",
        "коттеджн",
        "загородн",
        "усадьб",
        "реставрац",
        "историческ",
        "памятник",
        "спецификаци",
        "чертеж",
        "индивидуальн",
        "премиум",
        "элитн",
    ]

    # ── Маркеры высокого приоритета (crawl_status = "high") ──
    HIGH_PRIORITY_MARKERS: list[str] = [
        "hs-портал",
        "портал",
        "фахверк",
        "коттеджн",
        "остекление коттеджн",
        "по чертеж",
        "по спецификаци",
        "реставрац",
        "историческ",
        "памятник архитектур",
        "калевк",
        "горбылёк",
        "горбылек",
    ]

    # ── Стоп-слова для исключения ──────────────────────────
    EXCLUDE_KEYWORDS: list[str] = [
        "пвх",
        "пластиков",
        "пластик",
        "алюминиевые конструкции",
        "алюминиевые окна",
        "остекление балконов",
        "балкон",
        "лоджи",
    ]

    # ── Предохранители ──────────────────────────────────────
    MAX_PAGES_PER_CATEGORY: int = 50
    ITEMS_PER_PAGE: int = 20

    async def start_requests(self) -> AsyncGenerator[scrapy.Request, None]:
        for platform_name, config in self.PLATFORMS.items():
            for category in config["categories"]:
                url = f"{config['base']}{category}"
                cookies = self.SUPL_COOKIES if platform_name == "supl.biz" else None
                yield scrapy.Request(
                    url=url,
                    cookies=cookies,
                    callback=self.parse_listing,
                    meta={
                        "platform": platform_name,
                        "category_url": category,
                        "page": 1,
                    },
                    errback=self._on_error,
                )

    # ════════════════════════════════════════════════════════════
    # 1. Страница списка заявок
    # ════════════════════════════════════════════════════════════

    def parse_listing(
        self, response: Response
    ) -> Generator[scrapy.Request, None, None]:
        meta = response.meta
        platform: str = meta["platform"]

        if platform == "supl.biz":
            yield from self._parse_supl_listing(response)
        else:
            yield from self._parse_standard_listing(response)

        # Пагинация
        yield from self._paginate(response)

    # ── Supl.biz (обфусцированные классы, контент через текст) ──

    def _parse_supl_listing(
        self, response: Response
    ) -> Generator[scrapy.Request, None, None]:
        config = self.PLATFORMS["supl.biz"]
        cards = response.css(config["listing_selector"])

        if not cards:
            self.logger.info(
                "Supl.biz: нет карточек заказов на стр. %d",
                response.meta["page"],
            )
            return

        for card in cards:
            full_text = self._get_all_text(card).lower()

            if not any(kw in full_text for kw in self.TARGET_KEYWORDS):
                continue

            if self._is_excluded(full_text):
                continue

            # Извлекаем номер заказа → конструируем URL детальной страницы
            order_match = re.search(r"заказ\s*№\s*(\d+)", full_text)
            if not order_match:
                continue

            order_id = order_match.group(1)
            detail_url = f"{config['base']}/order/{order_id}/"

            yield scrapy.Request(
                url=detail_url,
                cookies=self.SUPL_COOKIES,
                callback=self.parse_detail,
                meta={
                    "platform": "supl.biz",
                    "title": f"Заказ №{order_id}",
                    "listing_text": full_text,
                },
                errback=self._on_error,
            )

    # ── Standard (fis.ru и др.: CSS-селекторы) ─────────────────

    def _parse_standard_listing(
        self, response: Response
    ) -> Generator[scrapy.Request, None, None]:
        meta = response.meta
        platform = meta["platform"]
        config = self.PLATFORMS[platform]

        items = response.css(config["listing_selector"])
        if not items:
            self.logger.info(
                "Нет элементов на стр. %d [%s] %s",
                meta["page"],
                platform,
                meta["category_url"],
            )
            return

        for item in items:
            title = item.css(config["title_selector"]).get() or ""
            desc = item.css(config["desc_selector"]).get() or ""
            href = item.css(config["link_selector"]).get()

            full_text = f"{title} {desc}".lower()

            if not any(kw in full_text for kw in self.TARGET_KEYWORDS):
                continue

            if self._is_excluded(full_text):
                continue

            if href:
                detail_url = urljoin(response.url, href)
                yield scrapy.Request(
                    url=detail_url,
                    callback=self.parse_detail,
                    meta={
                        "platform": platform,
                        "title": title.strip(),
                    },
                    errback=self._on_error,
                )

    def _paginate(
        self, response: Response
    ) -> Generator[scrapy.Request, None, None]:
        meta = response.meta
        current_page: int = meta["page"]
        next_page = current_page + 1

        if next_page > self.MAX_PAGES_PER_CATEGORY:
            return

        config = self.PLATFORMS[meta["platform"]]
        base_url = f"{config['base']}{meta['category_url']}".rstrip("/")

        if meta["platform"] == "supl.biz":
            next_url = f"{base_url}{config['paginate_query'].format(page=next_page)}"
        else:
            next_url = f"{base_url}{config['paginate'].format(page=next_page)}"

        cookies = self.SUPL_COOKIES if meta["platform"] == "supl.biz" else None
        yield scrapy.Request(
            url=next_url,
            cookies=cookies,
            callback=self.parse_listing,
            meta={
                "platform": meta["platform"],
                "category_url": meta["category_url"],
                "page": next_page,
            },
            errback=self._on_error,
        )

    @staticmethod
    def _get_all_text(element) -> str:
        """Извлечь весь текстовый контент из элемента (все потомки)."""
        parts = element.css("*::text").getall()
        return " ".join(p.strip() for p in parts if p.strip())

    # ════════════════════════════════════════════════════════════
    # 2. Детальная страница заявки
    # ════════════════════════════════════════════════════════════

    def parse_detail(
        self, response: Response
    ) -> Generator[scrapy.Request | ContactItem, None, None]:
        meta = response.meta
        platform: str = meta["platform"]

        if platform == "supl.biz":
            yield from self._parse_supl_detail(response)
        else:
            yield from self._parse_standard_detail(response)

    # ── Supl.biz: детальная страница (обфусцированный HTML) ────

    def _parse_supl_detail(
        self, response: Response
    ) -> Generator[scrapy.Request | ContactItem, None, None]:
        meta = response.meta
        body_text = self._get_all_text(response.css("body"))
        listing_text: str = meta.get("listing_text", "")

        full_text = f"{body_text} {listing_text}".lower()

        # Фильтрация
        if self._is_excluded(full_text):
            return

        if not any(kw in full_text for kw in self.TARGET_KEYWORDS):
            return

        is_high = any(marker in full_text for marker in self.HIGH_PRIORITY_MARKERS)

        # Контакты — только regex, т.к. классы рандомные
        phone = self._extract_phone_generic(response)
        email = self._extract_email_generic(response)

        # Название компании — ищем секцию "Информация о компании"
        company_name = self._extract_company_name_supl(response) or ""

        # Регион доставки
        region = self._extract_region_supl(response)

        # Рубрика
        rubric = self._build_rubric(full_text)

        # Описание — усекаем тело до разумного размера
        description = self._clean_text(body_text[:2000])

        item = ContactItem(
            company_name=company_name,
            description=description,
            category="Строительство",
            rubric=rubric,
            email=email,
            phone=phone,
            website_url=None,
            region=region,
            address=None,
            source="supl.biz",
            crawl_status="high" if is_high else "pending",
        )

        # Если нет контактов — ищем ссылку на профиль компании
        if not phone and not email:
            profile_url = self._find_supl_company_url(response)
            if profile_url:
                yield scrapy.Request(
                    url=urljoin(response.url, profile_url),
                    cookies=self.SUPL_COOKIES,
                    callback=self.parse_company_profile,
                    meta={"item": item},
                    errback=self._on_error,
                )
                return

        yield item

    # ── Standard (fis.ru): детальная страница с CSS-селекторами ─

    def _parse_standard_detail(
        self, response: Response
    ) -> Generator[scrapy.Request | ContactItem, None, None]:
        meta = response.meta
        platform: str = meta["platform"]

        title = self._extract_detail_title(response) or meta.get("title") or ""
        description = self._extract_detail_description(response)

        full_text = f"{title} {description}".lower()

        if self._is_excluded(full_text):
            return

        if not any(kw in full_text for kw in self.TARGET_KEYWORDS):
            return

        is_high = any(marker in full_text for marker in self.HIGH_PRIORITY_MARKERS)

        phone = self._extract_phone(response, platform)
        email = self._extract_email(response, platform)
        company_name = self._extract_company_name(response, platform) or title
        region = self._extract_region(response, platform)
        rubric = self._build_rubric(full_text)

        item = ContactItem(
            company_name=company_name,
            description=description[:1000] if description else "",
            category="Строительство",
            rubric=rubric,
            email=email,
            phone=phone,
            website_url=None,
            region=region,
            address=None,
            source=platform,
            crawl_status="high" if is_high else "pending",
        )

        if not phone and not email:
            company_url = self._extract_company_url(response, platform)
            if company_url:
                yield scrapy.Request(
                    url=urljoin(response.url, company_url),
                    callback=self.parse_company_profile,
                    meta={"item": item},
                    errback=self._on_error,
                )
                return

        yield item

    # ════════════════════════════════════════════════════════════
    # 3. Профиль компании (обогащение контактов)
    # ════════════════════════════════════════════════════════════

    def parse_company_profile(
        self, response: Response
    ) -> Generator[ContactItem, None, None]:
        item: ContactItem = response.meta["item"]

        # Дозаполняем контакты из профиля
        if not item.get("phone"):
            phone = self._extract_phone_generic(response)
            if phone:
                item["phone"] = phone

        if not item.get("email"):
            email = self._extract_email_generic(response)
            if email:
                item["email"] = email

        if not item.get("website_url"):
            site = response.css(
                "a[href^='http']:has(span:contains('Сайт')), "
                "a.website::attr(href), "
                ".site a::attr(href)"
            ).get()
            if site:
                item["website_url"] = site

        if not item.get("region"):
            addr = (
                response.css(".company-address::text, .address::text").get() or ""
            ).strip()
            if addr:
                item["region"] = self._guess_region(addr)

        yield item

    # ════════════════════════════════════════════════════════════
    #  Supl.biz-specific helpers
    # ════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_company_name_supl(response: Response) -> str | None:
        """Ищем 'Информация о компании' → берём следующий значимый текст."""
        html = response.text
        # Ищем h4 или div, содержащий "Информация о компании"
        # После него — название компании
        match = re.search(
            r'Информация\s+о\s+компании[^<]*<[^>]*>(.*?)<',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            candidate = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            if candidate and len(candidate) < 200:
                return candidate
        return None

    @staticmethod
    def _extract_region_supl(response: Response) -> str | None:
        """Ищем 'Поставка в' → извлекаем город/регион."""
        html = response.text
        match = re.search(
            r'Поставка\s+в\s+(?:город\s+)?([А-Яа-яЁё\-\s]+?)(?:<|\.)',
            html,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        # fallback: ищем "Центральный федеральный округ" и т.п.
        match = re.search(
            r'([А-Яа-яЁё]+\s+(?:федеральный\s+)?округ)',
            html,
            re.IGNORECASE,
        )
        return match.group(1) if match else None

    @staticmethod
    def _find_supl_company_url(response: Response) -> str | None:
        """Ищем ссылку на профиль компании на supl.biz."""
        for a in response.css("a::attr(href)").getall():
            if "/company/" in a or "/seller/" in a or "/supplier/" in a:
                return a
        return None

    @staticmethod
    def _clean_text(text: str) -> str:
        """Удалить лишние пробелы, обрезать."""
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:1500]

    # ════════════════════════════════════════════════════════════
    #  Методы извлечения (площадка-специфичные)
    # ════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_detail_title(response: Response) -> str | None:
        for sel in [
            "h1::text",
            "h2.page-title::text",
            ".object-title h1::text",
            ".tender-title h1::text",
        ]:
            val = response.css(sel).get()
            if val:
                return val.strip()
        return None

    @staticmethod
    def _extract_detail_description(response: Response) -> str:
        parts = []
        for sel in [
            ".description::text",
            ".object-description::text",
            ".tender-description::text",
            ".full-description::text",
            "article .content::text",
            "#description::text",
        ]:
            vals = response.css(sel).getall()
            if vals:
                parts.extend(v.strip() for v in vals if v.strip())
        return " ".join(parts)

    @staticmethod
    def _extract_phone(response: Response, platform: str) -> str | None:
        if platform == "fis.ru":
            sel = (
                "a[href^='tel:']::attr(href), "
                ".phone::text, "
                ".contact-phone::text, "
                "span.phones::text"
            )
        else:
            sel = (
                "a[href^='tel:']::attr(href), "
                ".phone::text, "
                ".request-phone::text, "
                "span.phone-number::text"
            )
        for s in sel.split(", "):
            val = response.css(s).get()
            if val:
                cleaned = re.sub(r"[^\d+]", "", val.replace("tel:", ""))
                if len(cleaned) >= 7:
                    return cleaned
        return None

    @staticmethod
    def _extract_email(response: Response, platform: str) -> str | None:
        if platform == "fis.ru":
            sel = (
                "a[href^='mailto:']::attr(href), "
                ".email::text, "
                ".contact-email::text"
            )
        else:
            sel = (
                "a[href^='mailto:']::attr(href), "
                ".email::text, "
                ".request-email::text"
            )
        for s in sel.split(", "):
            val = response.css(s).get()
            if val:
                return val.replace("mailto:", "").strip()
        return None

    @staticmethod
    def _extract_company_name(response: Response, platform: str) -> str | None:
        if platform == "fis.ru":
            sel = (
                ".company-name a::text, "
                ".org-name::text, "
                ".seller-name::text, "
                "a.company::text"
            )
        else:
            sel = (
                ".company-name::text, "
                ".request-company::text, "
                ".org-name::text"
            )
        for s in sel.split(", "):
            val = response.css(s).get()
            if val and val.strip():
                return val.strip()
        return None

    @staticmethod
    def _extract_company_url(response: Response, platform: str) -> str | None:
        if platform == "fis.ru":
            sel = (
                "a.company::attr(href), "
                "a.company-name::attr(href), "
                "a.seller-link::attr(href)"
            )
        else:
            sel = (
                "a.company-name::attr(href), "
                "a.org-link::attr(href)"
            )
        for s in sel.split(", "):
            val = response.css(s).get()
            if val:
                return val.strip()
        return None

    @staticmethod
    def _extract_region(response: Response, platform: str) -> str | None:
        if platform == "fis.ru":
            sel = (
                ".region::text, "
                ".city::text, "
                ".location::text, "
                "span.region-name::text"
            )
        else:
            sel = (
                ".region::text, "
                ".city::text, "
                ".request-city::text, "
                "span.city::text"
            )
        for s in sel.split(", "):
            val = response.css(s).get()
            if val and val.strip():
                return val.strip()
        return None

    @staticmethod
    def _extract_phone_generic(response: Response) -> str | None:
        html = response.text
        patterns = [
            r"\+7[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}",
            r"8[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}",
        ]
        for pat in patterns:
            match = re.search(pat, html)
            if match:
                cleaned = re.sub(r"[^\d+]", "", match.group(0))
                if len(cleaned) >= 7:
                    return cleaned
        return None

    @staticmethod
    def _extract_email_generic(response: Response) -> str | None:
        match = re.search(
            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            response.text,
        )
        return match.group(0) if match else None

    # ── Построение рубрики ─────────────────────────────────

    @staticmethod
    def _build_rubric(text: str) -> str:
        keywords = {
            "деревян": "Деревянные окна",
            "дуб": "Окна из дуба",
            "лиственниц": "Окна из лиственницы",
            "дерево-алюмин": "Дерево-алюминиевые окна",
            "алюминий-дерево": "Дерево-алюминиевые окна",
            "портал": "Портальные системы",
            "раздвижн": "Раздвижные системы",
            "фахверк": "Фахверк",
            "реставрац": "Реставрация",
            "фасадн": "Фасадные работы",
            "остеклен": "Остекление",
        }
        found = []
        for kw, label in keywords.items():
            if kw in text.lower():
                found.append(label)
        return "; ".join(found) if found else "Заявка на остекление"

    # ── Регион из текста ───────────────────────────────────

    @staticmethod
    def _guess_region(text: str) -> str | None:
        cities = [
            "Москва",
            "Санкт-Петербург",
            "Краснодар",
            "Новосибирск",
            "Екатеринбург",
            "Казань",
            "Нижний Новгород",
            "Самара",
            "Ростов-на-Дону",
            "Уфа",
            "Воронеж",
        ]
        for city in cities:
            if city.lower() in text.lower():
                return city
        return None

    # ── Фильтрация ─────────────────────────────────────────

    @staticmethod
    def _is_excluded(text: str) -> bool:
        if not text:
            return False
        t = text.lower()
        return any(kw.lower() in t for kw in B2BCatalogSpider.EXCLUDE_KEYWORDS)

    # ── Ошибки ─────────────────────────────────────────────

    @staticmethod
    def _on_error(failure) -> None:
        logger.error(
            "B2B request failed: %s",
            failure.request.url if failure.request else "unknown",
        )
