import re


def extract_address(text: str, logger) -> str | None:
    address_pattern = (
        r"(?:г\.|город|ул\.|улица|пр\-|проспект|обл\.|область)"
        r"\s?[А-Яа-я0-9\s\.,№\-]+"
    )
    addresses: list[str] = re.findall(address_pattern, text)
    if addresses:
        logger.debug(f"Адрес найден: {addresses[0].strip()}")
        return addresses[0].strip()
    logger.debug("Адрес не найден")
    return None
