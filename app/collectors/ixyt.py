import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import RawEvent
from app.collectors.generic_html import _category

SOURCE_NAME = "iXYt.info"
BASE_URL = "https://ixyt.info/ua/Ukraine/Ternopil"

_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})(?:\.(?P<year>20\d{2}))?"
    r"(?:,?\s*(?P<hour>\d{1,2}):(?P<minute>\d{2}))?"
)
_GENERIC = {"more", "детальніше", "квитки", "tickets"}


def _parse_start(text: str, now: datetime) -> datetime | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    group = match.groupdict()
    year = int(group["year"] or now.year)
    candidate = datetime(
        year,
        int(group["month"]),
        int(group["day"]),
        int(group["hour"] or 0),
        int(group["minute"] or 0),
    )
    if group["year"] is None and candidate < now.replace(hour=0, minute=0, second=0, microsecond=0):
        candidate = candidate.replace(year=year + 1)
    return candidate


def _id(url: str, title: str, start_at: datetime) -> str:
    return hashlib.sha256(f"{url}|{title}|{start_at.isoformat()}".encode()).hexdigest()[:32]


def _title(block: Tag, generic_anchor: Tag) -> str | None:
    for tag in block.select("h1, h2, h3, h4, h5, h6, [class*='title'], [class*='name'], strong, b"):
        text = " ".join(tag.stripped_strings).strip()
        if text and text.lower() not in _GENERIC:
            return text.strip(" —–|•")

    parts = [text.strip() for text in block.stripped_strings if text.strip()]
    for text in parts:
        if text.lower() in _GENERIC or _DATE_RE.search(text):
            continue
        return text.strip(" —–|•")
    return None


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

    anchors = soup.find_all("a", href=True)
    for anchor in anchors:
        anchor_text = " ".join(anchor.stripped_strings).strip().lower()
        if anchor_text not in _GENERIC:
            continue

        block: Tag | None = anchor
        selected: Tag | None = None
        for _ in range(6):
            if not isinstance(block, Tag):
                break
            text = " ".join(block.stripped_strings)
            if _DATE_RE.search(text) and 10 <= len(text) <= 2500:
                selected = block
                break
            block = block.parent
        if selected is None:
            continue

        text = " ".join(selected.stripped_strings)
        start_at = _parse_start(text, now)
        title = _title(selected, anchor)
        if not start_at or not title:
            continue

        href = urljoin(BASE_URL, anchor.get("href", ""))
        if not href.startswith("https://ixyt.info/") or href in seen:
            continue
        seen.add(href)
        result.append(
            RawEvent(
                external_id=_id(href, title, start_at),
                title=title,
                category=_category(text),
                start_at=start_at,
                venue=None,
                address=None,
                price_text=None,
                ticket_url=href if anchor_text in {"квитки", "tickets"} else None,
                source_url=href,
                description=text[:1500],
            )
        )
    return result
