import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import RawEvent

SOURCE_NAME = "KASA.com.ua"
BASE_URL = "https://kasa.com.ua/ternopol/"
_DATE_RE = re.compile(r"(?P<year>20\d{2})/(?P<month>\d{2})/(?P<day>\d{2})")
_TIME_RE = re.compile(r"Час початку\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})")
_PRICE_RE = re.compile(r"Ціна від\s*(?P<price>\d[\d ]*)\s*грн", re.I)
_GENERIC = {"придбати квиток", "подія вже відбулася", "особистий кабінет"}


def _parse_start(text: str) -> datetime | None:
    date_match = _DATE_RE.search(text)
    time_match = _TIME_RE.search(text)
    if not date_match or not time_match:
        return None
    try:
        return datetime(
            int(date_match["year"]),
            int(date_match["month"]),
            int(date_match["day"]),
            int(time_match["hour"]),
            int(time_match["minute"]),
        )
    except ValueError:
        return None


def _id(url: str, start_at: datetime) -> str:
    return hashlib.sha256(f"{url}|{start_at.isoformat()}".encode()).hexdigest()[:32]


def _event_card(anchor: Tag) -> Tag | None:
    block: Tag | None = anchor
    for _ in range(5):
        if not isinstance(block, Tag) or block.name in {"body", "html"}:
            return None
        text = " ".join(block.stripped_strings)
        if _DATE_RE.search(text) and _TIME_RE.search(text):
            return block
        block = block.parent
    return None


def _venue_from_card(card: Tag) -> str | None:
    parts = list(card.stripped_strings)
    for index, part in enumerate(parts):
        if _DATE_RE.search(part):
            candidates = [value.strip() for value in parts[:index] if value.strip()]
            for candidate in reversed(candidates):
                if candidate.lower() not in _GENERIC and not candidate.startswith("«"):
                    return candidate.strip(" |—–•") or None
            break
    return None


def _parse_venue_page(html: str, page_url: str, now: datetime) -> list[RawEvent]:
    soup = BeautifulSoup(html, "lxml")
    result: list[RawEvent] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href]"):
        title = " ".join(anchor.stripped_strings).strip()
        if title.startswith("«") and title.endswith("»"):
            title = title[1:-1].strip()
        if not title or title.lower() in _GENERIC:
            continue
        card = _event_card(anchor)
        if card is None:
            continue
        text = " ".join(card.stripped_strings)
        start_at = _parse_start(text)
        if start_at is None or start_at < now:
            continue
        href = anchor.get("href")
        if not href:
            continue
        source_url = urljoin(page_url, href)
        if source_url in seen:
            continue
        seen.add(source_url)
        price_match = _PRICE_RE.search(text)
        result.append(
            RawEvent(
                external_id=_id(source_url, start_at),
                title=title,
                category="Квиток/афіша",
                start_at=start_at,
                venue=_venue_from_card(card),
                address=None,
                price_text=(price_match.group(0).strip() if price_match else None),
                ticket_url=source_url,
                source_url=source_url,
                description=text[:1500],
            )
        )
    return result


def _venue_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    marker = next(
        (tag for tag in soup.find_all(["h2", "h3"]) if "Майданчики Тернопіль" in " ".join(tag.stripped_strings)),
        None,
    )
    if marker is None:
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for sibling in marker.find_all_next():
        if isinstance(sibling, Tag) and sibling.name in {"h1", "h2", "h3"} and "Квитки у Тернопіль" in " ".join(sibling.stripped_strings):
            break
        if not isinstance(sibling, Tag) or sibling.name != "a":
            continue
        href = sibling.get("href")
        title = " ".join(sibling.stripped_strings).strip()
        if not href or not title:
            continue
        url = urljoin(BASE_URL, href)
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def collect(timeout: float = 20.0) -> list[RawEvent]:
    now = datetime.now()
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
    venue_urls = _venue_urls(response.text)
    if not venue_urls:
        raise RuntimeError("KASA.com.ua city page did not expose the observed venue catalog structure")

    result: list[RawEvent] = []
    seen_ids: set[str] = set()
    with httpx.Client(
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
        },
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        for venue_url in venue_urls:
            venue_response = client.get(venue_url)
            venue_response.raise_for_status()
            for event in _parse_venue_page(venue_response.text, venue_url, now):
                if event.external_id in seen_ids:
                    continue
                seen_ids.add(event.external_id)
                result.append(event)
    return result
