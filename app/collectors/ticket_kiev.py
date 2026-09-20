from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent
from app.collectors.generic_html import parse_html

BASE_URL = "https://ticket.kiev.ua/ternopil/"
SOURCE_NAME = "Ticket.kiev.ua"

_CATEGORY_LABELS = {
    "концерт",
    "театр",
    "балет",
    "цирк",
    "стендап",
    "спорт",
    "дітям",
}
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
}


def _category_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls: set[str] = set()
    for anchor in soup.select("a[href]"):
        label = " ".join(anchor.stripped_strings).strip().lower()
        if label not in _CATEGORY_LABELS:
            continue
        url = urljoin(BASE_URL, anchor.get("href", ""))
        if url.startswith(BASE_URL) and url.rstrip("/") != BASE_URL.rstrip("/"):
            urls.add(url)
    return sorted(urls)


def collect(
    timeout: float = 20.0,
    now: datetime | None = None,
) -> list[RawEvent]:
    current_time = now or datetime.now()
    response = httpx.get(
        BASE_URL,
        headers=_HEADERS,
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()

    pages = [(BASE_URL, response.text)]
    for category_url in _category_urls(response.text):
        category_response = httpx.get(
            category_url,
            headers=_HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )
        category_response.raise_for_status()
        pages.append((category_url, category_response.text))

    events: dict[str, RawEvent] = {}
    for page_url, html in pages:
        for event in parse_html(html, page_url, now=current_time):
            if event.title.strip().lower() in _CATEGORY_LABELS:
                continue
            if event.start_at is None or event.start_at < current_time:
                continue
            events.setdefault(event.external_id, event)

    return list(events.values())
