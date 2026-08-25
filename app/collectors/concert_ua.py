from app.collectors.generic_jsonld import collect_jsonld

BASE_URL = "https://concert.ua/uk/catalog/ternopil/all-categories"
SOURCE_NAME = "Concert.ua"

CONCERT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://concert.ua/uk/ternopil",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
    ),
}


def collect(timeout: float = 20.0):
    return collect_jsonld(
        BASE_URL,
        SOURCE_NAME,
        timeout=timeout,
        headers=CONCERT_HEADERS,
    )
