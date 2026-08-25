from app.collectors.generic_html import collect_html

SOURCE_NAME = "MURAVA"
BASE_URL = "https://www.murava.life/"


def collect(timeout: float = 20.0):
    """Collect upcoming MURAVA PARK RELAX events from the official public site."""
    return collect_html(BASE_URL, source_name=SOURCE_NAME, timeout=timeout)
