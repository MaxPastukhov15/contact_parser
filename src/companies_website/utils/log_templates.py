class T:
    SKIP = "[SKIP]"
    RETRY_PW = "[RETRY-PW]"
    SPA = "[SPA?]"
    CONTACTS = "[CONTACTS]"
    SPIDER = "[SPIDER]"
    PERSISTENCE = "[PERSISTENCE]"
    WATCHDOG = "[WATCHDOG]"
    EXIT = "[EXIT]"
    FINDER = "[FINDER]"
    EMAIL = "[EMAIL]"
    EMAIL_NF = "[EMAIL NOT FOUND]"
    FINAL = "[FINAL]"
    CHECKPOINT = "[CHECKPOINT]"


class MSG:
    @staticmethod
    def found_records(n):
        return f"Found {n} records for updates"

    @staticmethod
    def blocked(domain, url):
        return f"{T.SKIP} Заблокирован: {domain} — {url}"

    @staticmethod
    def yield_done(n):
        return f"Yield loop finished. Total yielded: {n}"

    @staticmethod
    def ok(count, url, tag, kb, fields, filled):
        return f"[{count}] OK {url} {tag}({kb}KB,+{fields} полей, итого заполнено {filled}/4)"

    @staticmethod
    def skip(reason, url):
        return f"{reason} для {url} — пропускаем извлечение данных"

    @staticmethod
    def contact_page_skip(status, url):
        return f"{T.SKIP} Contact page {status} — {url} (страница не найдена)"

    @staticmethod
    def spa(url):
        return f"{T.SPA} Подозрение на JS-рендеринг: {url}"

    @staticmethod
    def contacts(n, urls):
        return f"{T.CONTACTS} {n} кандидатов: {urls}"

    @staticmethod
    def retry_pw(url, status):
        return f"{T.RETRY_PW} {url}: статус {status}, пробуем через Playwright"

    @staticmethod
    def err(count, url, status, msg):
        return f"[{count}] ERR {url}(status={status}): {msg}"

    @staticmethod
    def too_many(n):
        return f"{T.SPIDER} {n} ошибок подряд — закрываю"

    @staticmethod
    def progress(done, total, ok, err, fields, spa, contact_skipped):
        return (
            f"--- Прогресс: {done}/{total} обработано, OK={ok}, ERR={err}, "
            f"заполнено пол={fields}, suspected_spa={spa}, "
            f"contact_404={contact_skipped} ---"
        )

    # csv_persistence
    persistence_ready = f"{T.PERSISTENCE} Расширение готово, watchdog запланирован."
    watchdog_done = f"{T.WATCHDOG} Все запросы обработаны."

    @staticmethod
    def watchdog_force(elapsed, done, total):
        return (
            f"{T.WATCHDOG} Нет прогресса {elapsed:.0f}с — "
            f"обработано {done}/{total}, принудительное закрытие"
        )

    @staticmethod
    def watchdog_warn(elapsed, done, total):
        return f"{T.WATCHDOG} Нет прогресса {elapsed:.0f}с — обработано {done}/{total}"

    exit_nothing = f"{T.EXIT} Нечего сохранять аварийно."

    @staticmethod
    def exit_save(n):
        return f"{T.EXIT} Emergency save: {n} результатов"

    # csv_uow
    @staticmethod
    def written(tag, new, removed, total):
        return f"[{tag}] Записано {new} новых, удалено дублей: {removed}, всего в файле: {total}"

    @staticmethod
    def final_state(scraped, closing, busy):
        return f"{T.FINAL} state: scraped={scraped} spider_closing={closing} checkpoint_busy={busy}"
