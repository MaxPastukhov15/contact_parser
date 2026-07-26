import html
import re
from logging import Logger

from scrapy.http import HtmlResponse

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9\-._+]+@[a-zA-Z0-9\-._]+\.[a-zA-Z]{2,6}")
PRIORITY_PREFIXES = ("info@", "sales@", "mail@", "hello@", "office@")


def decode_cfemail(cfemail: str) -> str | None:
    """Декодирует Cloudflare email-protection (hex XOR)."""
    try:
        r = int(cfemail[:2], 16)
        decoded = "".join(chr(int(cfemail[i : i + 2], 16) ^ r) for i in range(2, len(cfemail), 2))
        return decoded if EMAIL_PATTERN.match(decoded) else None
    except (ValueError, IndexError):
        return None


def decode_obfuscated_text(text: str) -> str:
    """Раскодирует HTML-entities и схлопывает JS-конкатенацию строк."""
    if not text:
        return ""

    unescaped = html.unescape(text)

    cleaned = re.sub(r"['\"]\s*\+\s*['\"]", "", unescaped)
    cleaned = re.sub(r"\s*[\[\(]\s*at\s*[\]\)]\s*", "@", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*[\[\(]\s*dot\s*[\]\)]\s*", ".", cleaned, flags=re.I)
    return cleaned


def extract_email(response: HtmlResponse, text: str, logger: Logger) -> str | None:
    if not text:
        return None

    found_emails = []

    for href in response.css('a[href^="mailto:"]::attr(href)').getall():
        email = href.replace("mailto:", "").strip().split("?")[0]
        if bool(EMAIL_PATTERN.match(email)):
            found_emails.append(email)

    for cfemail in response.css("[data-cfemail]::attr(data-cfemail)").getall():
        decoded = decode_cfemail(cfemail)
        if decoded:
            logger.debug(f"[EMAIL] Email декодирован из Cloudflare protection: {decoded}")
            found_emails.append(decoded)

    if not found_emails:
        emails = EMAIL_PATTERN.findall(text)

        if not emails:
            decoded = decode_obfuscated_text(text)
            emails = EMAIL_PATTERN.findall(decoded)
            if emails:
                logger.debug("[EMAIL] Email извлечен из декодированного JS/Entities")
            found_emails.extend(emails)

    unique = list(set(found_emails))

    for email in unique:
        if email.startswith(PRIORITY_PREFIXES):
            logger.debug(f"[EMAIL] Email найден (приоритетный): {email}")
            return email

    if unique:
        logger.debug(f"[EMAIL] Email найден: {unique[0]}")
        return str(unique[0])

    logger.debug("[EMAIL NOT FOUND] Email не найден")
    return None
