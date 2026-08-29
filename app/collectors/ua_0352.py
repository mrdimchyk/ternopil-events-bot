import hashlib
import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import RawEvent
from app.collectors.generic_html import _category

SOURCE_NAME = "0352.ua"
BASE_URL = "https://www.0352.ua/afisha"

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
    r"(?P<day>\d{1,2})(?:\s*-\s*\d{1,2})?\s+(?P<month>" + "|".join(_MONTHS) + r")"
    r"(?:,?\s*(?P<hour>\d{1,2}):(?P<minute>\d{2}))?"
)


def _parse_start(text: str, page_date: date) -> datetime | None:
    match = _DATE_RE.search(text.lower())
    if not match:
        return None
    group = match.groupdict()
    month = _MONTHS[group["month"]]
    year = page_date.year
    if month < page_date.month - 6:
        year += 1
    return datetime(
        year,
        month,
        int(group["day"]),
        int(group["hour"] or 0),
        int(group["minute"] or 0),
    )


def _id(url: str, title: str, start_at: datetime) -> str:
    return hashlib.sha256(f"{url}|{title}|{start_at.isoformat()}".encode()).hexdigest()[:32]


def _extract_event(anchor: Tag, page_date: date) -> RawEvent | None:
    title = " ".join(anchor.stripped_strings).strip()
    href = urljoin(BASE_URL + "/", anchor.get("href", ""))
    if not title or not href.startswith("https://www.0352.ua/afisha/"):
        return None

    block: Tag | None = anchor
    selected: Tag | None = None
    for _ in range(6):
        if not isinstance(block, Tag):
            break
        text = " ".join(block.stripped_strings).strip()
        if _DATE_RE.search(text.lower()) and 10 <= len(text) <= 1800:
            selected = block
            break
        block = block.parent
    if selected is None:
        return None

    text = " ".join(selected.stripped_strings).strip()
    start_at = _parse_start(text, page_date)
    if start_at is None:
        return None

    return RawEvent(
        external_id=_id(href, title, start_at),
        title=title,
        category=_category(text),
        start_at=start_at,
        venue=None,
        address=None,
        price_text=None,
        ticket_url=None,
        source_url=href,
        description=text[:1500],
    )


def collect(timeout: float = 20.0, days: int = 14) -> list[RawEvent]:
    today = date.today()
    result: list[RawEvent] = []
    seen: set[str] = set()

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
    }

    for offset in range(days + 1):
        page_date = today + timedelta(days=offset)
        url = f"{BASE_URL}/{page_date.isoformat()}"
        response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        for anchor in soup.find_all("a", href=True):
            event = _extract_event(anchor, page_date)
            if event is None or event.external_id in seen:
                continue
            seen.add(event.external_id)
            result.append(event)

    return result
