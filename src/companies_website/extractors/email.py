import html
import re
from typing import Optional
from logging import Logger
from scrapy.http import HtmlResponse

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9\-._+]+@[a-zA-Z0-9\-._]+\.[a-zA-Z]{2,6}")
PRIORITY_PREFIXES = ("info@", "sales@", "mail@", "hello@", "office@")


def decode_obfuscated_text(text: str) -> str:
    """Раскодирует HTML-entities и схлопывает JS-конкатенацию строк."""
    if not text:
        return ""

    unescaped = html.unescape(text)

    cleaned = re.sub(r"['\"]\s*\+\s*['\"]", "", unescaped)
    return cleaned


def extract_email(response: HtmlResponse, text: str, logger: Logger) -> Optional[str]:
    if not text:
        return None

    found_emails = []

    for href in response.css('a[href^="mailto:"]::attr(href)').getall():
        email = href.replace("mailto:", "").strip().split("?")[0]
        if bool(EMAIL_PATTERN.match(email)):
            found_emails.append(email)

    if not found_emails:
        emails = EMAIL_PATTERN.findall(text)

        if not emails:
            decoded = decode_obfuscated_text(text)
            emails = EMAIL_PATTERN.findall(decoded)
            logger.debug("[EMAIL] Email извлечен из декодированного JS/Entities")

    if not found_emails:
        return None

    unique = list(set(found_emails))
    for email in unique:
        if email.startswith(PRIORITY_PREFIXES):
            logger.debug(f"[EMAIL] Email найден (приоритетный): {email}")
            return email

        logger.debug(f"[EMAIL] Email найден: {unique[0]}")
        return str(unique[0])

    logger.debug("[EMAIL NOT FOUND] Email не найден")
    return None
