from app.collectors.generic_jsonld import collect_jsonld

BASE_URL = "https://concert.ua/uk/catalog/ternopil/all-categories"
SOURCE_NAME = "Concert.ua"


def collect(timeout: float = 20.0):
    return collect_jsonld(BASE_URL, timeout=timeout)
