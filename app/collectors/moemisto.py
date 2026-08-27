import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import RawEvent
from app.collectors.generic_html import _category

SOURCE_NAME = "moemisto.ua"
BASE_URL = "https://moemisto.ua/te"

_MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5,
    "червня": 6, "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10,
    "листопада": 11, "грудня": 12,
}
_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\s+(?P<month>січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)"
    r"(?:\s+(?P<year>20\d{2}))?(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{2}))?",
    re.I,
)
_RANGE_RE = re.compile(
    r"(?P<day>\d{1,2})(?:\s*[-–]\s*(?P<end>\d{1,2}))?\s+(?P<month>січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)"
    r"(?:\s+(?P<year>20\d{2}))?",
    re.I,
)
_PRICE_RE = re.compile(r"(?:від\s*)?\d[\d\s]*(?:[.,]\d+)?\s*(?:₴|грн)", re.I)
_GENERIC = {"купити квиток", "купити", "детальніше", "всі", "читати далі"}


def _date_match(text: str) -> re.Match[str] | None:
    return _DATE_RE.search(text) or _RANGE_RE.search(text)


def _parse_start(text: str, now: datetime) -> datetime | None:
    match = _date_match(text)
    if not match:
        return None
    g = match.groupdict()
    day = int(g["day"])
    month = _MONTHS[g["month"].lower()]
    year = int(g["year"] or now.year)
    hour = int(g.get("hour") or 0)
    minute = int(g.get("minute") or 0)
    if g.get("year") is None and datetime(year, month, day, hour, minute) < now.replace(hour=0, minute=0, second=0, microsecond=0):
        year += 1
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def _id(url: str, title: str, start_at: datetime) -> str:
    return hashlib.sha256(f"{url}|{title}|{start_at.isoformat()}".encode()).hexdigest()[:32]


def _title(anchor: Tag, block: Tag) -> str | None:
    text = " ".join(anchor.stripped_strings).strip()
    if text and text.lower() not in _GENERIC:
        return text.strip(" —–|•")
    for tag in block.select("h1, h2, h3, h4, h5, [class*='title'], [class*='name']"):
        text = " ".join(tag.stripped_strings).strip()
        if text and text.lower() not in _GENERIC:
            return text.strip(" —–|•")
    return None


def _venue(text: str, title: str) -> str | None:
    match = _date_match(text)
    if not match:
        return None
    prefix = text[:match.start()].strip(" ,|•—–")
    if title:
        prefix = prefix.replace(title, "", 1).strip(" ,|•—–")
    prefix = re.sub(r"\bТернополі?\b", "", prefix, flags=re.I).strip(" ,|•—–")
    return prefix or None


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
    soup = BeautifulSoup(response.text, "lxml")
    now = datetime.now()
    result: list[RawEvent] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href]"):
        href = urljoin(BASE_URL, anchor.get("href", ""))
        if not href.startswith("https://moemisto.ua/te/") or href.rstrip("/") == BASE_URL.rstrip("/"):
            continue
        block: Tag | None = anchor
        selected: Tag | None = None
        for _ in range(6):
            if not isinstance(block, Tag):
                break
            text = " ".join(block.stripped_strings)
            if "тернопіль" in text.lower() and _date_match(text) and 30 <= len(text) <= 2200:
                selected = block
                break
            block = block.parent
        if selected is None:
            continue
        text = " ".join(selected.stripped_strings)
        start_at = _parse_start(text, now)
        title = _title(anchor, selected)
        if not start_at or not title or href in seen:
            continue
        seen.add(href)
        price = _PRICE_RE.search(text)
        low = text.lower()
        result.append(
            RawEvent(
                external_id=_id(href, title, start_at),
                title=title,
                category=_category(text),
                start_at=start_at,
                venue=_venue(text, title),
                address=None,
                price_text=price.group(0).strip() if price else None,
                ticket_url=href if "квит" in low or "купити" in low else None,
                source_url=href,
                description=text[:1500],
            )
        )
    return result
