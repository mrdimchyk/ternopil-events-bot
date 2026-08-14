from app.collectors.html_catalog import collect_html

BASE_URL = "https://ternopil.ticketsbox.com/"
SOURCE_NAME = "TicketsBox"

# TicketsBox exposes separate catalogue pages. The root page is mostly a
# marketing/top-events page and its JSON-LD does not contain the catalogue.
CATALOG_URLS = [
    f"{BASE_URL}concert/",
    f"{BASE_URL}theater/",
    f"{BASE_URL}razvlecheniya/",
    f"{BASE_URL}circus/",
    f"{BASE_URL}interaktivnij-zahid/",
    f"{BASE_URL}kultura-i-iskusstvo/",
    f"{BASE_URL}football/",
]


def collect(timeout: float = 20.0):
    return collect_html(CATALOG_URLS, timeout=timeout, min_future=True)
