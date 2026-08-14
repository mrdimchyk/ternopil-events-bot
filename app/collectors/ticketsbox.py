from datetime import datetime

from app.collectors.line_catalog import collect_line_catalog

BASE_URL = "https://ternopil.ticketsbox.com/"
_MONTH_SLUGS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def collect(timeout: float = 20.0):
    # Category pages are often cached with an old result set. The city month
    # pages contain the actual catalogue and are much more stable for scraping.
    now = datetime.now()
    urls = [BASE_URL]
    for offset in range(4):
        idx = now.month - 1 + offset
        urls.append(f"{BASE_URL}{_MONTH_SLUGS[idx % 12]}/")
    urls += [
        f"{BASE_URL}concert/",
        f"{BASE_URL}theater/",
        f"{BASE_URL}razvlecheniya/",
        f"{BASE_URL}interaktivnij-zahid/",
    ]
    return collect_line_catalog(urls, timeout=timeout)
