from logging import Logger

from scrapy.http import HtmlResponse

ABOUT_HEADINGS = [
    "О компании",
    "О нас",
    "Наша компания",
    "Описание",
    "Деятельность",
    "Профиль",
    "About Us",
    "About",
    "Чем мы занимаемся",
    "Миссия",
    "Кто мы",
    "Наша миссия",
    "О организации",
    "Информация о компании",
    "Наш профиль",
]


def extract_description(response: HtmlResponse, logger: Logger) -> str | None:
    meta_desc: str | None = response.css('meta[name="description"]::attr(content)').get()
    if meta_desc and len(meta_desc.strip()) > 10:
        logger.debug(f"Описание из meta: {meta_desc[:80]}...")
        return meta_desc.strip()

    og_desc: str | None = response.css('meta[property="og:description"]::attr(content)').get()
    if og_desc and len(og_desc.strip()) > 10:
        logger.debug(f"Описание из og:description: {og_desc[:80]}...")
        return og_desc.strip()

    heading_conditions = " or ".join(f'contains(text(), "{h}")' for h in ABOUT_HEADINGS)
    about_paragraphs = response.xpath(
        f"//descendant::*[{heading_conditions}]/following-sibling::p/text()"
    ).getall()

    if about_paragraphs:
        text = " ".join(p.strip() for p in about_paragraphs[:3] if p.strip())
        if text:
            logger.debug(f"Описание из заголовка: {text[:80]}...")
            return text

    about_text_nodes = response.xpath(
        f"//descendant::*[{heading_conditions}]/../following-sibling::*//text()"
    ).getall()
    about_text_nodes = [t.strip() for t in about_text_nodes if len(t.strip()) > 30]
    if about_text_nodes:
        text = " ".join(about_text_nodes[:3])
        if text:
            logger.debug(f"Описание из div-контента: {text[:80]}...")
            return text

    first_long_p = response.xpath(
        '//div[contains(@class, "content") or contains(@class, "main") or contains(@class, "about")]'
        "//p[string-length(text()) > 50]/text()"
    ).get()
    if first_long_p and len(first_long_p.strip()) > 50:
        logger.debug(f"Описание из контента: {first_long_p[:80]}...")
        return first_long_p.strip()

    return None
