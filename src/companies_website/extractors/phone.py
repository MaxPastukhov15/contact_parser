import re


def extract_phone(text: str, logger) -> str | None:
    phone_pattern = r"\+?[78]\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}"
    phones = re.findall(phone_pattern, text)
    if phones:
        raw_phone = re.sub(r"\D", "", phones[0])
        if raw_phone.startswith("8"):
            raw_phone = "7" + raw_phone[1:]
        if len(raw_phone) == 11:
            formatted = f"7-{raw_phone[1:4]}-{raw_phone[4:7]}-{raw_phone[7:9]}-{raw_phone[9:11]}"
            logger.debug(f"Телефон найден: {formatted}")
            return formatted
    logger.debug("Телефон не найден")
    return None
