import re
from logging import Logger

_ADDRESS_KEYWORDS = (
    r"(?:г\.|город|ул\.|улица|пр\-|проспект|обл\.|область|д\.|дом|кв\.|офис|корп\.|пер\.|ш\.)"
)
_ADDRESS_BODY = r"[А-Яа-я0-9 \t\.,№\-]{3,80}"
_ADDRESS_PATTERN = re.compile(_ADDRESS_KEYWORDS + r"\s?" + _ADDRESS_BODY)


def extract_address(text: str, logger: Logger) -> str | None:
    match = _ADDRESS_PATTERN.search(text)
    if match:
        address = match.group(0).strip()
        logger.debug(f"Адрес найден: {address}")
        return address
    logger.debug("Адрес не найден")
    return None
