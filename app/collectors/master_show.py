import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import RawEvent

SOURCE_NAME = "Master Show"
BASE_URL = "https://master-show.com/events"

_MONTHS = {
    "січень": 1, "січня": 1, "лютий": 2, "лютого": 2, "березень": 3, "березня": 3,
    "квітень": 4, "квітня": 4, "травень": 5, "травня": 5, "червень": 6, "червня": 6,
    "липень": 7, "липня": 7, "серпень": 8, "серпня": 8, "вересень": 9, "вересня": 9,
    "жовтень": 10, "жовтня": 10, "листопад": 11, "листопада": 11, "грудень": 12, "грудня": 12,
}
_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\s+(?P<month>січень|січня|лютий|лютого|березень|березня|квітень|квітня|травень|травня|червень|червня|липень|липня|серпень|серпня|вересень|вересня|жовтень|жовтня|листопад|листопада|грудень|грудня)"
    r"(?:\s+(?P<year>20\d{2}))?\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})",
    re.I,
)
_PRICE_RE = re.compile(r"від\s+(?P<price>[\d\s]+)\s*UAH", re.I)


def _parse_start(text: str, now: datetime) -> datetime | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    groups = match.groupdict()
    try:
        return datetime(int(groups["year"] or now.year), _MONTHS[groups["month"].lower()], int(groups["day"]), int(groups["hour"]), int(groups["minute"]))
    except (KeyError, ValueError):
        return None


def _id(url: str, start_at: datetime) -> str:
    return hashlib.sha256(f"{url}|{start_at.isoformat()}".encode()).hexdigest()[:32]


def _event_card(anchor: Tag) -> Tag | None:
    block: Tag | None = anchor
    for _ in range(6):
        if not isinstance(block, Tag):
            return None
        text = " ".join(block.stripped_strings)
        event_links = block.select('a[href*="/events/"]')
        if _DATE_RE.search(text) and len(event_links) == 1:
            return block if "Тернопіль" in text else None
        block = block.parent
    return None


def _venue(text: str) -> str | None:
    match = re.search(r"Тернопіль,\s*(.+?)(?=\s+від\s+[\d\s]+\s*UAH|$)", text, re.I)
    if not match:
        return None
    venue = match.group(1).strip(" |—–•")
    return venue[:255] if venue else None


def _collect_from_html(html: str, now: datetime | None = None) -> list[RawEvent]:
    now = now or datetime.now()
    soup = BeautifulSoup(html, "lxml")
    result: list[RawEvent] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href*="/events/"]'):
        href = anchor.get("href")
        if not href:
            continue
        card = _event_card(anchor)
        if card is None:
            continue
        text = " ".join(card.stripped_strings)
        start_at = _parse_start(text, now)
        if start_at is None or start_at < now:
            continue
        source_url = urljoin(BASE_URL, href)
        if source_url in seen:
            continue
        seen.add(source_url)
        title = " ".join(anchor.stripped_strings).strip()
        if not title:
            continue
        price_match = _PRICE_RE.search(text)
        result.append(RawEvent(external_id=_id(source_url, start_at), title=title, category="Концерт/подія", start_at=start_at, venue=_venue(text), address=None, price_text=f"від {price_match.group('price').strip()} UAH" if price_match else None, ticket_url=source_url, source_url=source_url, description=text[:1500]))
    return result


def collect(timeout: float = 20.0) -> list[RawEvent]:
    response = httpx.get(BASE_URL, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7"}, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return _collect_from_html(response.text)
