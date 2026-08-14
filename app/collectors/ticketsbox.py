from app.collectors.generic_jsonld import collect_jsonld

BASE_URL = "https://ternopil.ticketsbox.com/"
SOURCE_NAME = "TicketsBox"


def collect(timeout: float = 20.0):
    return collect_jsonld(BASE_URL, SOURCE_NAME, timeout=timeout)
