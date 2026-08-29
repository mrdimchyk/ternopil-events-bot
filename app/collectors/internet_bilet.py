import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import RawEvent

SOURCE_NAME = "Internet-bilet.ua"
BASE_URL = "https://ternopil.internet-bilet.ua/uk"

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
_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\s+(?P<month>січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)"
    r"(?:\s+(?P<year>20\d{2}))?,\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})",
    re.I,
)
_GENERIC = {"купити квитки", "детальніше", "всі заходи"}


def _parse_start(text: str, now: datetime) -> datetime | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    groups = match.groupdict()
    try:
        return datetime(
            int(groups["year"] or now.year),
            _MONTHS[groups["month"].lower()],
            int(groups["day"]),
            int(groups["hour"]),
            int(groups["minute"]),
        )
    except (KeyError, ValueError):
        return None


def _id(url: str, title: str, start_at: datetime) -> str:
    value = f"{url}|{title}|{start_at.isoformat()}"
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def _event_card(anchor: Tag) -> Tag | None:
    block: Tag | None = anchor
    for _ in range(6):
        if not isinstance(block, Tag):
            return None
        text = " ".join(block.stripped_strings)
        if "тернопіль" in text.lower() and _DATE_RE.search(text):
            return block
        block = block.parent
    return None


def _title(anchor: Tag) -> str:
    return " ".join(anchor.stripped_strings).strip()


def _venue(text: str) -> str | None:
    match = re.search(r"Тернопіль\s+(.+?)(?=(?:\s+від\s+\d|\s+\d[\d ]*\s*грн|\s+Залишилось|\s+Купити|\s+\d{1,2}\s+(?:січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)))", text, re.I)
    return match.group(1).strip(" |—–•") if match else None


def _price(text: str) -> str | None:
    match = re.search(r"(?:від\s+)?\d[\d ]*\s*грн", text, re.I)
    return match.group(0).strip() if match else None


def _collect_from_html(html: str, now: datetime | None = None) -> list[RawEvent]:
    now = now or datetime.now()
    soup = BeautifulSoup(html, "lxml")
    result: list[RawEvent] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href]"):
        title = _title(anchor)
        if not title or title.lower() in _GENERIC:
            continue
        card = _event_card(anchor)
        if card is None:
            continue
        text = " ".join(card.stripped_strings)
        start_at = _parse_start(text, now)
        if start_at is None or start_at < now:
            continue
        if "скасован" in text.lower() or "відміна заходу" in text.lower():
            continue
        href = anchor.get("href")
        if not href:
            continue
        source_url = urljoin(BASE_URL + "/", href)
        if source_url in seen:
            continue
        seen.add(source_url)
        result.append(
            RawEvent(
                external_id=_id(source_url, title, start_at),
                title=title,
                category="Квиток/афіша",
                start_at=start_at,
                venue=_venue(text),
                address=None,
                price_text=_price(text),
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
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
        },
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    return _collect_from_html(response.text)
