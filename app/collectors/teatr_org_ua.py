from app.collectors.html_catalog import collect_html

BASE_URL = "https://teatr.org.ua/cities/ternopil"
SOURCE_NAME = "Teatr.org.ua"


def collect(timeout: float = 20.0):
    return collect_html([BASE_URL], timeout=timeout, min_future=True)
