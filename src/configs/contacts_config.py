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
        "компания",
        "связаться",
        "реквизиты",
    ]

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

    BLOCKED_DOMAIN_KEYWORDS: ClassVar[tuple] = (
        "casino",
        "casinos",
        "slots",
        "slot",
        "gambl",
        "betting",
        "bet365",
        "bookmaker",
        "poker",
        "roulette",
        "jackpot",
        "казино",
        "ставк",
        "букмекер",
    )

    BLOCKED_CONTENT_KEYWORDS: ClassVar[tuple] = (
        "казино",
        "azino",
        "volcano",
        "вулкан",
        "игровые автоматы",
        "слоты",
        "джекпот",
        "букмекерская контора",
        "ставки на спорт",
        "online casino",
        "play casino",
        "gambling",
    )

    WAF_BODY_SIGNATURES: ClassVar[tuple[str, ...]] = (
        "cf-browser-verification",
        "cf-challenge",
        "cf_chl",
        "just a moment",
        "checking your browser",
        "please wait while we verify",
        "enable javascript and cookies",
        "please turn on javascript",
        "verify you are human",
        "hcaptcha",
        "h-captcha",
        "smartcaptcha",
        "smart-captcha",
        "access denied by",
        "blocked by",
        "access to this page has been denied",
    )

    WAF_URL_PATTERNS: ClassVar[tuple] = ("intruder_", "cf_chl_", "antibot")
    MAX_CONTACT_PAGES: ClassVar[int] = 3
