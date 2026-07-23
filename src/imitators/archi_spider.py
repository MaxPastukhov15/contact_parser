import logging
import re
from collections.abc import AsyncGenerator, Generator
from typing import Any
from urllib.parse import urljoin

import scrapy
from scrapy.http import Response

from src.companies_website.items import ContactItem

logger = logging.getLogger(__name__)


class ArchiSpider(scrapy.Spider):
    """Парсер archi.ru — каталог архитектурных бюро и проектов.

    ────────────────────────────────────────────────────────────
    Архитектура:
      1. Собирает все архитектурные бюро из /architects/russia
         (пагинация по start_p).
      2. Для каждого бюро парсит страницу → контакты, описание,
         команда архитекторов.
      3. Параллельно обходит /projects/russia в поиске объектов
         премиум-сегмента (виллы, коттеджи, усадьбы и т.д.).
      4. Если проект проходит по визуальным маркерам (панорамное
         остекление, дерево-алюминий и т.п.) — собирает ссылку
         на бюро-автор и тоже парсит его (Scrapy сам дедуплицирует).
      5. На выходе — ContactItem со статусом:
         - "premium" если у бюро найдены премиальные проекты
         - "pending" если бюро есть в каталоге (базовый сбор)
    ────────────────────────────────────────────────────────────
    """

    name = "archi"
    allowed_domains: list[str] = ["archi.ru"]

    custom_settings = {
        "FEEDS": {
            "output/leads_archi.csv": {
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
    }

    # ── Стартовые точки обхода ──────────────────────────────
    # 1. Список архитекторов/бюро (Россия)
    # 2. Список проектов (Россия) — для поиска премиум-объектов
    START_URLS: list[str] = [
        "https://archi.ru/architects/russia",
        "https://archi.ru/projects/russia",
    ]

    # ── Типы объектов премиум-сегмента ──────────────────────
    PREMIUM_OBJECT_TYPES: list[str] = [
        "вилла",
        "коттедж",
        "усадьба",
        "особняк",
        "таунхаус",
        "реставрация",
    ]

    # ── Визуальные маркеры в описании проектов ──────────────
    PREMIUM_VISUAL_MARKERS: list[str] = [
        "панорамн",
        "безрамн",
        "дерево-алюмини",
        "алюминий-дерево",
        "деревоалюмини",
        "зимний сад",
        "радиусн",
        "арочн",
        "фахверк",
        "фасад из лиственниц",
        "деревянн",
        "французск",
    ]

    # ── Стоп-слова (широкие, т.к. archi.ru — про архитектуру) ──
    EXCLUDE_KEYWORDS: list[str] = [
        "пвх",
        "пластиков",
    ]

    # ── Предохранители пагинации ────────────────────────────
    MAX_ARCHITECT_PAGES: int = 200
    MAX_PROJECT_PAGES: int = 200

    # ── Размер страницы (стартовый offset) ──────────────────
    # archi.ru использует ?start_p=N — это номер первого элемента на странице
    # (0, 28, 56, …)
    PAGE_SIZE: int = 28

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._premium_studio_ids: set[str] = set()

    # ── Запуск ──────────────────────────────────────────────

    async def start_requests(self) -> AsyncGenerator[scrapy.Request, None]:
        for url in self.START_URLS:
            yield scrapy.Request(
                url=url,
                callback=self._route,
                errback=self._on_error,
            )

    def _route(self, response: Response) -> Generator[scrapy.Request, None, None]:
        """Маршрутизация: определяем, список архитекторов это или список проектов."""
        if "/architects/" in response.url:
            yield from self.parse_architects_list(response)
        elif "/projects/" in response.url:
            yield from self.parse_projects_list(response)

    # ════════════════════════════════════════════════════════════
    # 1. Парсинг списка архитекторов /architects/russia
    # ════════════════════════════════════════════════════════════

    def parse_architects_list(
        self, response: Response
    ) -> Generator[scrapy.Request, None, None]:
        """Извлекает ссылки на студии и пагинирует."""
        studio_links: set[str] = set()
        for article in response.css("div.article8"):
            # Ссылка на студию: a.addLink с href /architects/russiastudios/ID
            studio_href = article.css("a.addLink::attr(href)").get()
            if studio_href:
                full_url = urljoin(response.url, studio_href)
                studio_links.add(full_url)

        for link in studio_links:
            yield scrapy.Request(
                url=link,
                callback=self.parse_studio,
                errback=self._on_error,
            )

        # Пагинация
        yield from self._paginate_architects(response)

    def _paginate_architects(
        self, response: Response
    ) -> Generator[scrapy.Request, None, None]:
        """Пагинация через ?start_p=N (следующая страница)."""
        # Считаем сколько .article8 на странице
        items_on_page = len(response.css("div.article8"))
        if items_on_page == 0:
            return

        # Извлекаем текущий start_p из URL
        current_start = self._get_start_p(response.url)

        # Если набрали меньше, чем PAGE_SIZE — это последняя страница
        if items_on_page < self.PAGE_SIZE:
            return

        next_start = current_start + self.PAGE_SIZE
        if next_start // self.PAGE_SIZE > self.MAX_ARCHITECT_PAGES:
            return

        next_url = self._set_start_p(response.url, next_start)
        if next_url:
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_architects_list,
                errback=self._on_error,
            )

    # ════════════════════════════════════════════════════════════
    # 2. Парсинг списка проектов /projects/russia
    # ════════════════════════════════════════════════════════════

    def parse_projects_list(
        self, response: Response
    ) -> Generator[scrapy.Request, None, None]:
        """Обходит проекты и ищет премиум-объекты."""
        for article in response.css("div.article9"):
            project_url = article.css("div.photo a::attr(href)").get()
            if project_url:
                full_url = urljoin(response.url, project_url)
                yield scrapy.Request(
                    url=full_url,
                    callback=self.parse_project,
                    errback=self._on_error,
                )

        # Пагинация
        yield from self._paginate_projects(response)

    def _paginate_projects(
        self, response: Response
    ) -> Generator[scrapy.Request, None, None]:
        items_on_page = len(response.css("div.article9"))
        if items_on_page == 0:
            return

        current_start = self._get_start_p(response.url)
        if items_on_page < self.PAGE_SIZE:
            return

        next_start = current_start + self.PAGE_SIZE
        if next_start // self.PAGE_SIZE > self.MAX_PROJECT_PAGES:
            return

        next_url = self._set_start_p(response.url, next_start)
        if next_url:
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_projects_list,
                errback=self._on_error,
            )

    # ════════════════════════════════════════════════════════════
    # 3. Детальная страница проекта
    # ════════════════════════════════════════════════════════════

    def parse_project(
        self, response: Response
    ) -> Generator[scrapy.Request, None, None]:
        """Проверяет проект на маркеры премиума.
        Если проект подходит — парсим студию-автора."""
        title = response.css("h1[itemprop='name']::text").get() or ""
        description = response.css("div[itemprop='description']::text").get() or ""

        full_text = f"{title} {description}".lower()

        # Проверка типов объектов
        has_premium_type = any(
            t in full_text for t in self.PREMIUM_OBJECT_TYPES
        )

        # Проверка визуальных маркеров
        has_visual_markers = any(
            m in full_text for m in self.PREMIUM_VISUAL_MARKERS
        )

        if not (has_premium_type or has_visual_markers):
            return

        # Определяем тип объекта из .right-info
        object_type = self._extract_type_from_project(response)

        # Если явно не премиум-тип — пропускаем (защита от ложных срабатываний)
        if not has_premium_type and not self._is_premium_type(object_type):
            return

        # Извлекаем ссылки на студии с этой страницы проекта
        studio_links = self._extract_studio_links(response)
        for studio_url in studio_links:
            sid = self._studio_id_from_url(studio_url)
            if sid and sid not in self._premium_studio_ids:
                self._premium_studio_ids.add(sid)
                yield scrapy.Request(
                    url=studio_url,
                    callback=self.parse_studio,
                    meta={"premium_context": object_type or "премиум-проект"},
                    errback=self._on_error,
                )

    # ════════════════════════════════════════════════════════════
    # 4. Детальная страница студии (архитектурного бюро)
    # ════════════════════════════════════════════════════════════

    def parse_studio(self, response: Response) -> Generator[ContactItem, None, None]:
        """Извлекает контакты архитектурного бюро."""
        meta = response.meta
        premium_context = meta.get("premium_context")
        is_premium = bool(premium_context) or self._check_studio_projects_for_premium(
            response
        )

        # ── Название ───────────────────────────────────────────
        company_name = response.css("h1[itemprop='name']::text").get() or ""
        company_name = company_name.strip()

        alt_name = response.css("h3::text").get() or ""
        if alt_name:
            alt_name = alt_name.strip().lstrip("/").strip()
            if alt_name and alt_name != company_name:
                company_name = f"{company_name} / {alt_name}"

        if not company_name:
            return

        # ── Описание ───────────────────────────────────────────
        description_parts = response.css(
            "div[itemprop='description']::text"
        ).getall()
        description = " ".join(p.strip() for p in description_parts if p.strip())

        # ── Контакты (телефон, email, адрес) ───────────────────
        contacts_text = response.css("div.contacts").get()
        phone = self._extract_phone(contacts_text) if contacts_text else None
        email = self._extract_email(contacts_text) if contacts_text else None

        # ── Адрес ──────────────────────────────────────────────
        address = self._extract_address(contacts_text) if contacts_text else None

        # ── Сайт ───────────────────────────────────────────────
        website = response.css(
            "ul.info-list22 a.blue[target='_blank']::attr(href)"
        ).get()
        if not website:
            website = response.css(
                "li:has(h5:contains('Сайт')) a::attr(href)"
            ).get()

        # ── Город / Регион ────────────────────────────────────
        city = response.css(
            "ul.info-list22 li:has(h5:contains('Город')) span.blue::text"
        ).get()
        if not city:
            city = response.css(
                "li:has(h5:contains('Город')) span.blue::text"
            ).get()

        region = city.strip() if city else None
        if address and not region:
            region = self._guess_region_from_address(address)

        # ── Рубрики / категории ───────────────────────────────
        rubric_parts = []
        rubric = response.css(
            "ul.info-list22 li:has(h5:contains('Город')) span.blue::text"
        ).getall()
        if rubric:
            rubric_parts.extend(r.strip() for r in rubric)

        # Извлечение специализации из описания
        specialization = self._extract_specialization(description)

        # ── Команда (ГАПы / главные архитекторы) ──────────────
        team = self._extract_team(response)
        if team:
            rubric_parts.append("Команда: " + "; ".join(team))

        rubric_str = "; ".join(p for p in rubric_parts if p)

        # ── Собираем ContactItem ──────────────────────────────
        crawl_status = "premium" if is_premium else "pending"
        yield ContactItem(
            company_name=company_name,
            description=specialization or description[:500] if description else "",
            category="Архитектура / Проектирование",
            rubric=rubric_str or "Архитектурное бюро",
            email=email,
            phone=phone,
            website_url=website,
            region=region,
            address=address,
            source="archi.ru",
            crawl_status=crawl_status,
        )

    # ════════════════════════════════════════════════════════════
    #  Утилиты
    # ════════════════════════════════════════════════════════════

    # ── Пагинация ──────────────────────────────────────────────

    @staticmethod
    def _get_start_p(url: str) -> int:
        """Извлекает start_p из URL (по умолчанию 0)."""
        match = re.search(r"start_p=(\d+)", url)
        return int(match.group(1)) if match else 0

    @staticmethod
    def _set_start_p(url: str, start_p: int) -> str | None:
        """Меняет или добавляет start_p в URL."""
        if "start_p=" in url:
            new_url = re.sub(r"start_p=\d+", f"start_p={start_p}", url)
        elif "?" in url:
            new_url = f"{url}&start_p={start_p}"
        else:
            new_url = f"{url}?start_p={start_p}"
        return new_url

    # ── Парсинг контактов ──────────────────────────────────────

    @staticmethod
    def _extract_phone(html: str) -> str | None:
        """Ищет телефон в блоке .contacts."""
        match = re.search(
            r"тел\.?\s*[.:]?\s*([+\d][\d\s\-().]{6,20})", html
        )
        if match:
            raw = match.group(1).strip()
            cleaned = re.sub(r"[^\d+]", "", raw)
            return cleaned if len(cleaned) >= 7 else None
        return None

    @staticmethod
    def _extract_email(html: str) -> str | None:
        """Ищет email mailto: в блоке .contacts."""
        match = re.search(r'mailto:([^"\']+)', html)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_address(html: str) -> str | None:
        """Извлекает адрес из .contacts (до тел. и email)."""
        # Удаляем теги
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()

        # Ищем часть до "тел." или "E-mail"
        for sep in ["тел.", "e-mail", "E-mail"]:
            idx = text.lower().find(sep.lower())
            if idx != -1:
                text = text[:idx].strip()
                break

        # Убираем "Контакты:"
        text = re.sub(r"^Контакты\s*[:\-]?\s*", "", text, flags=re.IGNORECASE).strip()
        return text if text and len(text) > 5 else None

    # ── Парсинг команды ────────────────────────────────────────

    @staticmethod
    def _extract_team(response: Response) -> list[str]:
        """Извлекает ФИО архитекторов из .article11."""
        team = []
        for article in response.css("div.article11"):
            name = article.css("h2 a::text").get()
            role = article.css("div::text").get()
            if name:
                name = name.strip()
                if role:
                    role = role.strip()
                    team.append(f"{name} ({role})" if role else name)
                else:
                    team.append(name)
        return team

    # ── Определение специализации ─────────────────────────────

    @staticmethod
    def _extract_specialization(text: str) -> str | None:
        """Извлекает краткую специализацию: ищет первое предложение с ключевыми
        словами (архитектурное бюро, проектирование, строительство и т.д.)."""
        if not text:
            return None
        # Берём первый абзац или первые 300 символов
        first_part = text[:300]
        # Ищем первое предложение
        sentences = re.split(r"[.!?]\s+", first_part)
        for s in sentences:
            s = s.strip()
            if any(
                kw in s.lower()
                for kw in [
                    "архитектур",
                    "проект",
                    "бюро",
                    "студи",
                    "мастерск",
                ]
            ):
                return s[:200] if len(s) > 200 else s
        return first_part[:200] if first_part else None

    # ── Проверка типа объекта ──────────────────────────────────

    @staticmethod
    def _extract_type_from_project(response: Response) -> str | None:
        """Извлекает тип объекта со страницы проекта."""
        type_text = response.css(
            "ul.info-list li:has(h5)::text"
        ).get()
        if not type_text:
            type_text = response.css(
                "ul.info-list li:has(h5:contains('Тип')) *::text"
            ).getall()
            type_text = " ".join(t.strip() for t in type_text if t.strip())
        return type_text.strip() if type_text else None

    def _is_premium_type(self, object_type: str | None) -> bool:
        if not object_type:
            return False
        ot = object_type.lower()
        return any(t in ot for t in self.PREMIUM_OBJECT_TYPES)

    # ── Извлечение ссылок на студии из проекта ─────────────────

    @staticmethod
    def _extract_studio_links(response: Response) -> list[str]:
        """Ищет ссылки на студии в блоке авторов проекта."""
        links = []
        for article in response.css("div.article8"):
            studio_href = article.css(
                "a[href*='/architects/russiastudios/']::attr(href)"
            ).get()
            if studio_href:
                links.append(urljoin(response.url, studio_href))
        return links

    @staticmethod
    def _studio_id_from_url(url: str) -> str | None:
        """Извлекает ID студии из URL /russiastudios/ID."""
        match = re.search(r"/russiastudios/(\d+)", url)
        return match.group(1) if match else None

    # ── Проверка проектов студии на премиум-маркеры ────────────

    def _check_studio_projects_for_premium(self, response: Response) -> bool:
        """Быстрая проверка названий проектов на странице студии."""
        for article in response.css("div.article9"):
            title = article.css("h2 a::text").get() or ""
            sect = article.css("div.sect a::text").get() or ""
            full = f"{title} {sect}".lower()
            if any(t in full for t in self.PREMIUM_OBJECT_TYPES):
                return True
        return False

    # ── Регион из адреса ───────────────────────────────────────

    @staticmethod
    def _guess_region_from_address(address: str) -> str | None:
        """Пытается угадать регион из адреса."""
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
            if city.lower() in address.lower():
                return city
        return None

    # ── Фильтрация стоп-слов ───────────────────────────────────

    @staticmethod
    def _is_excluded(text: str) -> bool:
        if not text:
            return False
        t = text.lower()
        return any(kw in t for kw in ArchiSpider.EXCLUDE_KEYWORDS)

    # ── Обработка ошибок ───────────────────────────────────────

    @staticmethod
    def _on_error(failure) -> None:
        logger.error(
            "Request failed: %s",
            failure.request.url if failure.request else "unknown",
        )
