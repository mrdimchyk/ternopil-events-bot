import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent
from app.collectors.generic_html import _category, _parse_datetime

BASE_URL = "https://ticket.dp.ua/ternopil/"
SOURCE_NAME = "Ticket.dp.ua"
MONTH_RE = r"січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня"


def _id(url: str, title: str, start_at: datetime | None) -> str:
    value = start_at.isoformat() if start_at else ""
    return hashlib.sha256(f"{url}|{title}|{value}".encode()).hexdigest()[:32]


def collect(timeout: float = 20.0) -> list[RawEvent]:
    """Collect the event-card contract used by Ticket.dp.ua's Ternopil page."""
    response = httpx.get(
        BASE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
        },
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    result: list[RawEvent] = []
    seen_urls: set[str] = set()
    date_re = re.compile(
        rf"\b\d{{1,2}}\s+(?:{MONTH_RE})\s+20\d{{2}}\s*\(\d{{1,2}}:\d{{2}}\)",
        re.I,
    )

    for anchor in soup.select("a[href]"):
        href = urljoin(BASE_URL, anchor.get("href", ""))
        if not href.startswith(("http://", "https://")):
            continue
        text = " ".join(anchor.stripped_strings)
        match = date_re.search(text)
        if not match:
            continue
        start_at = _parse_datetime(text, now=datetime.now())
        if not start_at or href in seen_urls:
            continue
        title = text[:match.start()].strip(" —–|•")
        title = re.sub(r"^\d[\d\s]*\s+", "", title).strip()
        venue = text[match.end():].strip(" —–|•")
        if not title or not venue:
            continue
        price_match = re.match(r"^(\d[\d\s]*)\s+", text)
        price_text = f"{price_match.group(1).strip()} грн" if price_match else None
        result.append(
            RawEvent(
                external_id=_id(href, title, start_at),
                title=title,
                category=_category(title),
                start_at=start_at,
                venue=venue,
                address=None,
                price_text=price_text,
                ticket_url=href,
                source_url=href,
                description=None,
            )
        )
        seen_urls.add(href)

    return result
