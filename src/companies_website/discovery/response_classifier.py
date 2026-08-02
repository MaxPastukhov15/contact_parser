from __future__ import annotations

from src.configs.contacts_config import ContactsFinderSettings


def classify_response(response, html_text: str) -> str | None:
    final_url = response.url.lower()
    if any(p in final_url for p in ContactsFinderSettings.AUTH_URL_PATTERNS):
        return f"[AUTH] Редирект на страницу авторизации: {response.url}"

    if "intruder_" in response.url:
        return "[WAF] Anti-bot защита (intruder)"

    if any(kw in html_text.lower() for kw in ContactsFinderSettings.BLOCKED_CONTENT_KEYWORDS):
        return "[CONTENT] Заблокировано по контенту"

    waf_sig = is_waf_body(html_text)
    if waf_sig:
        return f"[WAF] Anti-bot защита ({waf_sig})"

    return None


def classify_error(
    status: int | None,
    body: str,
    playwright_retry: bool,
) -> tuple[str | None, bool]:
    if status in (403, 503) and not playwright_retry:
        waf_sig = is_waf_body(body) if body else None
        if waf_sig:
            return f"[WAF] Anti-bot защита ({waf_sig})", False
        if status == 503:
            return "[WAF] Сервер вернул 503, пропускаем", False
        return None, True

    if status == 403 and playwright_retry:
        return "[WAF] Playwright тоже заблокирован (403)", False

    return None, False


def is_waf_body(html_text: str) -> str | None:
    lowered = html_text.lower()
    for sig in ContactsFinderSettings.WAF_BODY_SIGNATURES:
        if sig in lowered:
            return sig
    return None
