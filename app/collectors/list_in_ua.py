from app.collectors.generic_html import collect_html

SOURCE_NAME = "List.in.ua"
BASE_URL = "https://list.in.ua/%D0%A2%D0%B5%D1%80%D0%BD%D0%BE%D0%BF%D1%96%D0%BB%D1%8C/afisha/soon"


def collect(timeout: float = 20.0):
    """Collect upcoming Ternopil events from List.in.ua's public HTML catalog."""
    return collect_html(BASE_URL, source_name=SOURCE_NAME, timeout=timeout)
