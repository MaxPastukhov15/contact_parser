import re

_STRIP_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.S | re.I)
_VISIBLE_TEXT_STRIP = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")

_SPA_MARKERS = (
    'id="root">',
    "id='root'>",
    'id="app">',
    "id='app'>",
    "__next_data__",
    "data-reactroot",
    "ng-version",
    "please enable javascript",
    "you need to enable javascript",
    "включите javascript",
)

# Если HTML заметно больше "нормального", а видимого текста почти нет —
# похоже на пустой SPA-контейнер, который заполняется уже в браузере.
_MIN_HTML_LEN_TO_CHECK = 2000
_MAX_VISIBLE_TEXT_FOR_SUSPECT = 200


def looks_js_rendered(html_text: str) -> bool:
    lowered = html_text.lower()
    if any(marker in lowered for marker in _SPA_MARKERS):
        return True

    if len(html_text) < _MIN_HTML_LEN_TO_CHECK:
        return False

    visible_text = _STRIP_SCRIPT_STYLE.sub(" ", html_text)
    visible_text = _VISIBLE_TEXT_STRIP.sub(" ", visible_text)
    visible_text = _WHITESPACE.sub(" ", visible_text).strip()
    return len(visible_text) < _MAX_VISIBLE_TEXT_FOR_SUSPECT
