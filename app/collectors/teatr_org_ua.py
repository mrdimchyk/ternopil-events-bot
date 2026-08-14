from app.collectors.line_catalog import collect_line_catalog

SOURCE_NAME = "Teatr.org.ua"
BASE_URL = "https://teatr.org.ua/cities/ternopil"


def collect(timeout: float = 20.0):
    return collect_line_catalog([BASE_URL], timeout=timeout)
