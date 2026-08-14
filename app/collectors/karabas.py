from datetime import datetime

from app.collectors.html_catalog import collect_html

BASE_URL = "https://ternopil.karabas.com/"

_MONTH_SLUGS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]


def collect(timeout: float = 20.0):
    """Collect Karabas events from month pages.

    The Karabas root currently returns HTTP 403 to GitHub Actions runners,
    while public month/category pages remain crawlable. Avoid the blocked
    root and fetch the current month plus the next five months instead.
    """
    now = datetime.now()
    urls = []
    for offset in range(6):
        month_index = now.month - 1 + offset
        year = now.year + month_index // 12
        month = month_index % 12
        urls.append(f"{BASE_URL}{_MONTH_SLUGS[month]}/")

    return collect_html(urls, timeout=timeout, min_future=True)
