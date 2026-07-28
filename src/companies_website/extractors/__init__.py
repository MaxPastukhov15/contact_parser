from .address import extract_address
from .description import extract_description
from .email import extract_email
from .phone import extract_phone

FIELDS = ("Чем занимается", "Адрес офиса", "Номер телефона", "Электронный адрес")
FIELD_EXTRACTORS = {
    "Чем занимается": lambda resp, _text, log: extract_description(resp, log),
    "Адрес офиса": lambda _resp, text, log: extract_address(text, log),
    "Номер телефона": lambda _resp, text, log: extract_phone(text, log),
    "Электронный адрес": lambda resp, text, log: extract_email(resp, text, log),
}


__all__ = [
    "extract_address",
    "extract_description",
    "extract_email",
    "extract_phone",
    "FIELDS",
    "FIELD_EXTRACTORS",
]
