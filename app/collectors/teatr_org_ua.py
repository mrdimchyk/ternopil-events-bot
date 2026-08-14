from app.collectors.generic_jsonld import collect_jsonld

BASE_URL = "https://teatr.org.ua/cities/ternopil"
SOURCE_NAME = "Teatr.org.ua"


def collect(timeout: float = 20.0):
    return collect_jsonld(BASE_URL, timeout=timeout)
