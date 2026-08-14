import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import RawEvent

MONTHS = {
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
    r"(?P<day>\d{1,2})[./-](?P<month>\d{1,2})[./-](?P<year>20\d{2})"
    r"\s*(?:р\.?\s*)?(?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"|"
    r"(?P<day2>\d{1,2})\s+(?P<month_name>січня|лютого|березня|квітня|травня|"
    r"червня|липня|серпня|вересня|жовтня|листопада|грудня)"
    r"(?:\s+(?P<year2>20\d{2}))?\s*(?:р\.?\s*)?"
    r"(?P<hour2>\d{1,2}):(?P<minute2>\d{2})",
    re.I,
)

_PRICE_RE = re.compile(r"(?:від\s*)?(\d[\d\s]*)\s*(?:₴|грн)", re.I)
_GENERIC_LINK_TEXT = {"квитки", "купити", "детальніше", "читати далі", "купити квиток"}


def _id(url: str, name: str, start: datetime | None) -> str:
    value = start.isoformat() if start else ""
    return hashlib.sha256(f"{url}|{name}|{value}".encode()).hexdigest()[:32]


def _parse_datetime(text: str, now: datetime | None = None) -> datetime | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    groups = match.groupdict()
    if groups["day"]:
        day = int(groups["day"])
        month = int(groups["month"])
        year = int(groups["year"])
        hour = int(groups["hour"])
        minute = int(groups["minute"])
    else:
        day = int(groups["day2"])
        month = MONTHS[groups["month_name"].lower()]
        year = int(groups["year2"] or (now or datetime.now()).year)
        hour = int(groups["hour2"])
        minute = int(groups["minute2"])
        if groups["year2"] is None and now is not None:
            candidate = datetime(year, month, day, hour, minute)
            if candidate < now.replace(hour=0, minute=0, second=0, microsecond=0):
                year += 1
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def _category(text: str) -> str | None:
    low = text.lower()
    if "стендап" in low:
        return "standup"
    if "театр" in low or "вистав" in low:
        return "theatre"
    if "фестив" in low:
        return "festival"
    if "концерт" in low:
        return "concert"
    return None


def _title_from_block(block: Tag, anchor: Tag) -> str | None:
    candidates: list[str] = []
    for tag in block.select("h1, h2, h3, h4, h5, [class*='title'], [class*='name']"):
        text = " ".join(tag.stripped_strings)
        if text and text.lower() not in _GENERIC_LINK_TEXT:
            candidates.append(text)
    anchor_text = " ".join(anchor.stripped_strings)
    if anchor_text and anchor_text.lower() not in _GENERIC_LINK_TEXT:
        candidates.append(anchor_text)
    if not candidates:
        return None
    candidates.sort(key=lambda value: (len(value), value), reverse=True)
    title = candidates[0]
    title = re.sub(r"^(Концерт|Театр|Стендап|Дітям)\s+", "", title, flags=re.I)
    return title.strip(" —–|•") or None


def collect_html(
    url: str,
    source_name: str | None = None,
    timeout: float = 20.0,
) -> list[RawEvent]:
    """Collect event cards from server-rendered HTML when JSON-LD is absent."""
    _ = source_name
    response = httpx.get(
        url,
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
    now = datetime.now()
    result: list[RawEvent] = []
    seen_urls: set[str] = set()

    for anchor in soup.select("a[href]"):
        href = urljoin(url, anchor.get("href", ""))
        if not href.startswith(("http://", "https://")) or href == url:
            continue
        anchor_text = " ".join(anchor.stripped_strings)
        if anchor_text.lower() in _GENERIC_LINK_TEXT:
            # The useful title is normally in the surrounding event card.
            pass

        block: Tag | None = anchor
        selected: Tag | None = None
        for _ in range(6):
            if not isinstance(block, Tag):
                break
            text = " ".join(block.stripped_strings)
            if (
                "тернопіль" in text.lower()
                and _DATE_RE.search(text)
                and 50 <= len(text) <= 1800
            ):
                selected = block
                break
            block = block.parent
        if selected is None:
            continue

        block_text = " ".join(selected.stripped_strings)
        start_at = _parse_datetime(block_text, now=now)
        if not start_at:
            continue
        title = _title_from_block(selected, anchor)
        if not title or title.lower() in _GENERIC_LINK_TEXT:
            continue

        price_match = _PRICE_RE.search(block_text)
        price_text = price_match.group(0).strip() if price_match else None
        low = block_text.lower()
        venue = None
        for marker in ("тернопіль",):
            idx = low.find(marker)
            if idx >= 0:
                tail = block_text[idx + len(marker):].strip(" ,|•—–")
                venue = re.split(r"\s+від\s+\d|\s+квитки\b", tail, maxsplit=1, flags=re.I)[0].strip()
                if venue:
                    break

        if href in seen_urls:
            continue
        seen_urls.add(href)
        result.append(
            RawEvent(
                external_id=_id(href, title, start_at),
                title=title,
                category=_category(block_text),
                start_at=start_at,
                venue=venue or None,
                address=None,
                price_text=price_text,
                ticket_url=href,
                source_url=href,
                description=None,
            )
        )

    return list({event.external_id: event for event in result}.values())
