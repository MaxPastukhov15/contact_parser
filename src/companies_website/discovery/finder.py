from urllib.parse import urlparse

from src.configs.contacts_config import ContactsFinderSettings


class ContactPageFinder:
    def __init__(self, logger):
        self.logger = logger

    def find_pages(self, response, current_path: str) -> list[str]:
        seen: set[str] = set()
        scored: list[tuple[int, str]] = []

        for score, url in self._scan_links_scored(response, current_path):
            if url in seen:
                continue

            seen.add(url)
            scored.append((score, url))

        self.logger.debug(f"[FINDER] Из ссылок: {len(scored)} кандидатов")

        scored.sort(key=lambda x: x[0], reverse=True)
        result = [url for _, url in scored[: ContactsFinderSettings.MAX_CONTACT_PAGES]]

        self.logger.debug(f"[FINDER] Итого: {result}")
        return result

    def _scan_links_scored(self, response, current_path: str) -> list[tuple[int, str]]:
        current_domain = response.meta.get("domain", "")
        candidates = []
        seen = set()

        for link in response.css("a"):
            href = link.attrib.get("href", "")

            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            if urlparse(href).path.lower().endswith(ContactsFinderSettings.IGNORE_EXTENSIONS):
                continue

            link_text = " ".join(link.css("::text").getall()).strip().lower()
            href_lower = href.lower()

            if not self._matches_contact_keyword(href_lower, link_text):
                continue

            full_url = response.urljoin(href)
            parsed = urlparse(full_url)
            link_domain = parsed.netloc.replace("www.", "")
            link_path = parsed.path.rstrip("/")

            if link_domain != current_domain:
                continue
            if link_path == current_path or link_path == "":
                continue
            if parsed.scheme not in ("http", "https"):
                continue
            if full_url in seen:
                continue

            seen.add(full_url)
            priority = self._score_candidate(href_lower, link_text, parsed)
            candidates.append((priority, full_url))

        return candidates

    def _matches_contact_keyword(self, href_lower: str, link_text: str) -> bool:
        for kw in ContactsFinderSettings.CONTACT_PAGE_KEYWORDS:
            if kw in href_lower or kw in link_text:
                return True
        return False

    def _score_candidate(self, href_lower: str, link_text: str, parsed) -> int:  # noqa: ARG002
        score = 0
        path = parsed.path.lower().rstrip("/")

        if path in ("/contacts", "/contact", "/kontakty"):
            score += 10
        elif path in ("/about", "/about-us", "/o-nas", "/o-kompanii", "/team"):
            score += 5
        elif "contact" in path or "контакт" in path or "team" in path:
            score += 7

        for kw in ("контакт", "contact", "о компании", "команд"):
            if kw in link_text:
                score += 3
                break

        return score
