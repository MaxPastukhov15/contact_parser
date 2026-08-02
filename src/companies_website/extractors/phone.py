import re
from logging import Logger

_PHONE_PATTERN = re.compile(r"\+?[78]\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}")


def extract_phone(text: str, logger: Logger) -> str | None:
    phones = _PHONE_PATTERN.findall(text)
    for phone in phones:
        raw_phone = re.sub(r"\D", "", phone)
        if raw_phone.startswith("8"):
            raw_phone = "7" + raw_phone[1:]
        if len(raw_phone) == 11:
            formatted = f"7-{raw_phone[1:4]}-{raw_phone[4:7]}-{raw_phone[7:9]}-{raw_phone[9:11]}"
            logger.debug(f"Телефон найден: {formatted}")
            return formatted
    logger.debug("Телефон не найден")
    return None
