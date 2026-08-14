from app.collectors.generic_html import collect_html

BASE_URL = "https://numotamo.com/uk/catalog/ternopil/all-categories"
SOURCE_NAME = "Numotamo"


def collect(timeout: float = 20.0):
    return collect_html(BASE_URL, SOURCE_NAME, timeout=timeout)
