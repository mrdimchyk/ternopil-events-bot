import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent
from app.collectors.generic_html import _category, _parse_datetime

BASE_URL = "https://ticketsfest.com.ua/en/events/ternopil/"
SOURCE_NAME = "TicketsFest"
DATE_RE = re.compile(r"\b\d{1,2}\.\d{1,2}\.20\d{2}\s*[·•]\s*\d{1,2}:\d{2}\b")
PRICE_RE = re.compile(r"(?:from|від)\s*([\d\s]+)\s*₴", re.I)


def _id(url: str, title: str, start_at: datetime | None) -> str:
    value = start_at.isoformat() if start_at else ""
    return hashlib.sha256(f"{url}|{title}|{value}".encode()).hexdigest()[:32]


def _parse_cards(html: str, now: datetime | None = None) -> list[RawEvent]:
    soup = BeautifulSoup(html, "lxml")
    result: list[RawEvent] = []
    seen_urls: set[str] = set()
    now = now or datetime.now()

    for heading in soup.find_all(["h2", "h3"]):
        title = " ".join(heading.stripped_strings)
        if not title:
            continue
        container = heading
        card_text = ""
        for _ in range(5):
            container = container.parent
            if container is None:
                break
            card_text = " ".join(container.stripped_strings)
            if DATE_RE.search(card_text) and "Ternopil" in card_text:
                break
        match = DATE_RE.search(card_text)
        if not match:
            continue
        start_at = _parse_datetime(match.group(0).replace("·", " "), now=now)
        if not start_at:
            continue

        link = heading.find_parent("a", href=True)
        if link is None:
            link = container.find("a", href=lambda href: href and "/events/" in href)
        if link is None:
            continue
        href = urljoin(BASE_URL, link.get("href", ""))
        if href in seen_urls:
            continue

        lines = [line.strip() for line in container.stripped_strings if line.strip()]
        venue = next((line for line in lines if line.startswith("Ternopil · ")), "")
        venue = venue.removeprefix("Ternopil · ").strip()
        if not venue:
            continue
        price_match = PRICE_RE.search(card_text)
        price_text = f"{price_match.group(1).strip()} ₴" if price_match else None

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


def collect(timeout: float = 20.0) -> list[RawEvent]:
    """Collect the live Ternopil event-card contract from TicketsFest."""
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
    return _parse_cards(response.text)
