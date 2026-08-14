from app.collectors.generic_html import collect_html

BASE_URL = "https://ticket.kiev.ua/ternopil/"
SOURCE_NAME = "Ticket.kiev.ua"


def collect(timeout: float = 20.0):
    return collect_html(BASE_URL, SOURCE_NAME, timeout=timeout)
