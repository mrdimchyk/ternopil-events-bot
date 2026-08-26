from app.collectors.generic_html import collect_html

BASE_URL = "https://afisha-ukraine.com/?city=14"
SOURCE_NAME = "Afisha-Ukraine"


def collect(timeout: float = 20.0):
    return collect_html(BASE_URL, SOURCE_NAME, timeout=timeout)
