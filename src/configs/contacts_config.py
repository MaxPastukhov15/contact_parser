from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ContactsFinderSettings:
    CONTACT_PAGE_KEYWORDS: ClassVar[list] = [
        "контакт",
        "contact",
        "about",
        "о нас",
        "о компании",
        "связь",
        "обратная",
        "офис",
        "addresses",
    ]

    CONTACT_PATHS: ClassVar[list] = [
        "/contacts",
        "/contact",
        "/about",
        "/about-us",
        "/about/contacts",
        "/kontakty",
        "/kontakt",
        "/o-nas",
        "/o-kompanii",
        "/requisites",
        "/contact-us",
        "/contact_us",
        "/index.php?page=contact",
        "/index.php?page=contacts",
        "/?page=contact",
        "/?page=contacts",
        "/index.php?option=com_contact",
        "/index.php?cat=contacts",
        "/info/contacts",
        "/info/contact",
        "/company/contacts",
        "/company/contact",
    ]

    PHP_PAGE_PARAMS: ClassVar[tuple] = (
        "page",
        "id",
        "view",
        "option",
        "cat",
        "p",
        "content",
        "item",
        "action",
    )

    AUTH_URL_PATTERNS: ClassVar[tuple] = (
        "passport",
        "login",
        "auth",
        "sso",
        "accounts.google",
        "oauth",
        "signin",
        "log-in",
    )

    BLOCKED_DOMAINS: ClassVar[list] = [
        "vk.com",
        "t.me",
        "telegram.me",
        "instagram.com",
        "facebook.com",
        "youtube.com",
        "dzen.ru",
        "passport.yandex.ru",
        "sso.passport.yandex.ru",
        "jivo.chat",
        "jivosite.ru",
        "whatsapp.com",
        "api.whatsapp.com",
        "max.ru",
        "2gis.ru",
        "go.2gis.com",
        "taplink.cc",
        "taplink.ws",
        "pulscen.ru",
        "avito.ru",
        "yell.ru",
        "zoon.ru",
        "vk.link",
        "tilda.ws",
        ".tb.ru",
    ]

    IGNORE_EXTENSIONS: ClassVar[tuple] = (
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".webp",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".css",
        ".js",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".mp4",
        ".mp3",
        ".zip",
        ".rar",
    )

    MAX_CONTACT_PAGES: ClassVar[int] = 3
