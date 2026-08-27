import hashlib
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import RawEvent
from app.collectors.generic_html import _parse_datetime

SOURCE_NAME = "MURAVA"
BASE_URL = "https://www.murava.life/"
VENUE = "MURAVA PARK RELAX"


def _id(url: str, title: str, start_at: datetime | None) -> str:
    value = start_at.isoformat() if start_at else ""
    return hashlib.sha256(f"{url}|{title}|{value}".encode()).hexdigest()[:32]


def collect(timeout: float = 20.0) -> list[RawEvent]:
    """Collect upcoming MURAVA events from the official public event block."""
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
    seen: set[str] = set()
    date_re = re.compile(
        r"\b\d{1,2}\s+(?:січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\s+20\d{2}\b",
        re.I,
    )

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if "concert.ua" not in href.lower():
            continue
        block: Tag | None = anchor
        selected: Tag | None = None
        for _ in range(8):
            if not isinstance(block, Tag):
                break
            text = " ".join(block.stripped_strings)
            if date_re.search(text):
                selected = block
                break
            block = block.parent
        if selected is None:
            continue

        text = " ".join(selected.stripped_strings)
        # The official MURAVA card currently publishes a date without a time.
        # Preserve the observed contract by treating a date-only event as midnight.
        parse_text = text if re.search(r"\b\d{1,2}:\d{2}\b", text) else f"{text} 00:00"
        start_at = _parse_datetime(parse_text, now=datetime.now())
        if not start_at:
            continue

        title = None
        for image in selected.select("img[alt]"):
            alt = " ".join(image.get("alt", "").split()).strip()
            if alt and not alt.lower().startswith("image"):
                title = alt
                break
        if not title:
            heading = selected.select_one("h1, h2, h3, h4, h5")
            if heading:
                title = " ".join(heading.stripped_strings).strip()
        if not title or title.lower() in {"купити квиток", "купити"}:
            continue

        key = _id(href, title, start_at)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            RawEvent(
                external_id=key,
                title=title,
                category="concert",
                start_at=start_at,
                venue=VENUE,
                address="с. Великі Гаї, вул. Чумацька, 30",
                price_text=None,
                ticket_url=href,
                source_url=BASE_URL,
                description=None,
            )
        )

    return result
