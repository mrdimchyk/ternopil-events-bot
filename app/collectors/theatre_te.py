import hashlib
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent
from app.collectors.generic_html import _category

BASE_URL = "https://www.theatre.te.ua/repertory"
SOURCE_NAME = "Тернопільський академічний театр ім. Т. Г. Шевченка"
_MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}
_DATE_RE = re.compile(
    r"(?P<dow>пн|вт|ср|чт|пт|сб|нд),?\s*(?P<day>\d{1,2})\s+(?P<month>січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\s+(?P<year>20\d{2})\s*(?:р\.?\s*)?(?P<hour>\d{1,2}):(?P<minute>\d{2})",
    re.I,
)
_PRICE_RE = re.compile(r"₴\s*([\d\s]+(?:-[\d\s]+)?)")


def _id(start_at: datetime, title: str) -> str:
    return hashlib.sha256(f"{BASE_URL}|{start_at.isoformat()}|{title}".encode()).hexdigest()[:32]


def _clean(text: str) -> str:
    return " ".join(text.split()).strip()


def _parse_date(text: str) -> datetime | None:
    match = _DATE_RE.search(_clean(text))
    if not match:
        return None
    try:
        return datetime(
            int(match.group("year")),
            _MONTHS[match.group("month").lower()],
            int(match.group("day")),
            int(match.group("hour")),
            int(match.group("minute")),
        )
    except (KeyError, ValueError):
        return None


def _parse_cards(html: str, now: datetime) -> list[RawEvent]:
    soup = BeautifulSoup(html, "lxml")
    result: list[RawEvent] = []
    seen: set[tuple[str, datetime]] = set()

    for heading in soup.find_all(["h2", "h3", "h4", "h5"]):
        title = _clean(heading.get_text(" "))
        if not title or title.lower() in {"репертуар", "найближчі події"}:
            continue

        date_text = ""
        for parent in [heading.parent, *heading.parents]:
            text = _clean(parent.get_text(" "))
            if _DATE_RE.search(text):
                date_text = text
                break
            if len(text) > 1000:
                break
        if not date_text:
            continue

        start_at = _parse_date(date_text)
        if not start_at or start_at < now:
            continue

        price_match = _PRICE_RE.search(date_text)
        price_text = price_match.group(1).strip() if price_match else None
        key = (title, start_at)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            RawEvent(
                external_id=_id(start_at, title),
                title=title,
                category=_category(title),
                start_at=start_at,
                venue=SOURCE_NAME,
                address="бульвар Тараса Шевченка, 6, Тернопіль",
                price_text=price_text,
                ticket_url=None,
                source_url=BASE_URL,
                description="Джерело: Тернопільський академічний театр ім. Т. Г. Шевченка",
            )
        )
    return result


def collect(timeout: float = 20.0) -> list[RawEvent]:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/139 Safari/537.36",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
    }
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        response = client.get(BASE_URL)
        response.raise_for_status()
        return _parse_cards(response.text, datetime.now())
