import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import RawEvent
from app.collectors.generic_html import _category

BASE_URL = "https://pulselive.com.ua/kontserty"
SOURCE_NAME = "Pulse Live"
_MONTHS = {
    "січня": 1,
    "лютого": 2,
    "березня": 3,
    "квітня": 4,
    "травня": 5,
    "червня": 6,
    "липня": 7,
    "серпня": 8,
    "вересня": 9,
    "жовтня": 10,
    "листопада": 11,
    "грудня": 12,
}
_DATE_TEXT_RE = re.compile(
    r"(?P<day>\d{1,2})\s+(?P<month>січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\s+(?P<year>20\d{2})\s*[·•]\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})",
    re.I,
)
_PRICE_RE = re.compile(r"Квитки\s*від\s*(?P<price>\d[\d ]*)\s*₴", re.I)


def _id(url: str, start_at: datetime) -> str:
    return hashlib.sha256(f"{url}|{start_at.isoformat()}".encode()).hexdigest()[:32]


def _event_block(anchor: Tag) -> Tag | None:
    text = " ".join(anchor.stripped_strings)
    if "Тернопіль" in text and _DATE_TEXT_RE.search(text):
        return anchor
    return None


def _title(block: Tag, anchor: Tag) -> str | None:
    for tag in block.select("h2, h3, h4"):
        text = " ".join(tag.stripped_strings).strip()
        if text:
            return text
    text = " ".join(anchor.stripped_strings).strip()
    return text or None


def _parse_datetime(text: str) -> datetime | None:
    match = _DATE_TEXT_RE.search(text)
    if not match:
        return None
    groups = match.groupdict()
    try:
        return datetime(
            int(groups["year"]),
            _MONTHS[groups["month"].lower()],
            int(groups["day"]),
            int(groups["hour"]),
            int(groups["minute"]),
        )
    except (KeyError, ValueError):
        return None


def _parse(html: str, page_url: str, now: datetime) -> list[RawEvent]:
    soup = BeautifulSoup(html, "lxml")
    result: list[RawEvent] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href]"):
        block = _event_block(anchor)
        if block is None:
            continue
        text = " ".join(block.stripped_strings)
        start_at = _parse_datetime(text)
        if not start_at or start_at < now or "Тернопіль" not in text:
            continue
        href = anchor.get("href")
        if not href:
            continue
        source_url = urljoin(page_url, href)
        if source_url in seen:
            continue
        title = _title(block, anchor)
        if not title:
            continue
        venue_match = re.search(r"Тернопіль\s*[·•]\s*(.+?)(?=\s+(?:Квитки|Дивитися|Обрати)\b)", text)
        venue = venue_match.group(1).strip() if venue_match else None
        price_match = _PRICE_RE.search(text)
        seen.add(source_url)
        result.append(
            RawEvent(
                external_id=_id(source_url, start_at),
                title=title,
                category=_category(text),
                start_at=start_at,
                venue=venue,
                address=None,
                price_text=(f"Квитки від {price_match['price'].strip()} ₴" if price_match else None),
                ticket_url=source_url,
                source_url=source_url,
                description=text[:1500],
            )
        )
    return result


def collect(timeout: float = 20.0) -> list[RawEvent]:
    response = httpx.get(
        BASE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
        },
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    return _parse(response.text, str(response.url), datetime.now())
