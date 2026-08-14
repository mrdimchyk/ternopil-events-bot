from app.collectors.generic_jsonld import collect_jsonld

BASE_URL = "https://ticket.kiev.ua/ternopil/"
SOURCE_NAME = "Ticket.kiev.ua"


def collect(timeout: float = 20.0):
    return collect_jsonld(BASE_URL, timeout=timeout)
