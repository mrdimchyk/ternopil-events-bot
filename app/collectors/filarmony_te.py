import hashlib
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent
from app.collectors.generic_html import _category

BASE_URL = "https://filarmony.te.ua/"
SOURCE_NAME = "Тернопільська обласна філармонія"
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
    r"(?P<day>\d{1,2})\s*(?P<month>січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)"
    r"(?:\s+(?P<year>20\d{2}))?.*?(?P<hour>\d{1,2})[:.](?P<minute>\d{2})",
    re.I,
)
_PRICE_RE = re.compile(r"Ціна\s+квитків:\s*([^<\n]+)", re.I)


def _id(start_at: datetime, title: str) -> str:
    return hashlib.sha256(f"{BASE_URL}|{start_at.isoformat()}|{title}".encode()).hexdigest()[:32]


def _clean(text: str) -> str:
    return " ".join(text.split()).strip(" -—:")


def _parse_date(text: str, default_year: int) -> datetime | None:
    match = _DATE_RE.search(_clean(text))
    if not match:
        return None
    try:
        return datetime(
            int(match.group("year") or default_year),
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

    headings = [
        (_clean(node.get_text(" ")), node)
        for node in soup.find_all(["h1", "h2", "h3", "h4"])
        if _clean(node.get_text(" "))
    ]
    heading_by_node = {id(node): title for title, node in headings}
    nodes = list(soup.find_all(string=True))

    for index, node in enumerate(nodes):
        text = _clean(str(node))
        start_at = _parse_date(text, now.year)
        if not start_at or start_at < now:
            continue

        title = None
        current = node.parent
        for parent in [current, *current.parents]:
            if id(parent) in heading_by_node:
                title = heading_by_node[id(parent)]
                break
            parent_headings = [
                heading
                for heading in parent.find_all(["h1", "h2", "h3", "h4"])
                if heading in heading_by_node
                and nodes.index(heading.string) < index
                if heading.string is not None
            ]
            if parent_headings:
                title = heading_by_node[id(parent_headings[-1])]
                break
        if not title:
            for previous in reversed(nodes[max(0, index - 12) : index]):
                candidate = _clean(str(previous))
                if not candidate or _parse_date(candidate, now.year):
                    continue
                if candidate.lower().startswith(("афіша", "новини", "ціна квитків", "квитки у касі", "довідки")):
                    continue
                if len(candidate) >= 8:
                    title = candidate
                    break
        if not title:
            continue

        price_match = _PRICE_RE.search(text)
        price_text = price_match.group(1).strip(" .") if price_match else None
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
                address="вул. Острозького, 11, Тернопіль",
                price_text=price_text,
                ticket_url=None,
                source_url=BASE_URL,
                description="Джерело: Тернопільська обласна філармонія",
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
