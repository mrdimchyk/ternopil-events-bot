import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import RawEvent

SOURCE_NAME = "Kvytok"
BASE_URL = "https://kvytok.co/ternopil/"

_MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5,
    "червня": 6, "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10,
    "листопада": 11, "грудня": 12,
}
_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})[.\s]+(?P<month>\d{1,2}|січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)"
    r"(?:[.\s]+(?P<year>20\d{2}))?\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})",
    re.I,
)
_GENERIC = {"квитки", "купити квиток", "детальніше"}


def _parse_start(text: str, now: datetime) -> datetime | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    g = match.groupdict()
    month_token = g["month"].lower()
    month = int(month_token) if month_token.isdigit() else _MONTHS[month_token]
    year = int(g["year"] or now.year)
    try:
        return datetime(year, month, int(g["day"]), int(g["hour"]), int(g["minute"]))
    except ValueError:
        return None


def _id(url: str, title: str, start_at: datetime) -> str:
    return hashlib.sha256(f"{url}|{title}|{start_at.isoformat()}".encode()).hexdigest()[:32]


def _card_for_title(title_tag: Tag) -> Tag | None:
    block: Tag | None = title_tag
    for _ in range(5):
        if not isinstance(block, Tag):
            return None
        text = " ".join(block.stripped_strings)
        if "тернопіль" in text.lower() and _DATE_RE.search(text) and "квитки" in text.lower():
            return block
        block = block.parent
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

    for title_tag in soup.select("h5"):
        title = " ".join(title_tag.stripped_strings).strip()
        if not title or title.lower() in _GENERIC:
            continue
        card = _card_for_title(title_tag)
        if card is None:
            continue
        text = " ".join(card.stripped_strings)
        start_at = _parse_start(text, now)
        if start_at is None or start_at < now or title.lower() in _GENERIC:
            continue

        ticket_anchor = next(
            (a for a in card.select("a[href]") if "квит" in " ".join(a.stripped_strings).lower()),
            None,
        )
        source_url = urljoin(BASE_URL, ticket_anchor.get("href")) if ticket_anchor else BASE_URL
        if source_url in seen:
            continue
        seen.add(source_url)

        lower = text.lower()
        city_pos = lower.find("тернопіль")
        venue = None
        if city_pos >= 0:
            tail = text[city_pos + len("Тернопіль"):]
            venue = re.split(r"\bквитки\b", tail, maxsplit=1, flags=re.I)[0].strip(" |—–•") or None

        result.append(
            RawEvent(
                external_id=_id(source_url, title, start_at),
                title=title,
                category="Квиток/афіша",
                start_at=start_at,
                venue=venue,
                address=None,
                price_text=None,
                ticket_url=source_url,
                source_url=source_url,
                description=text[:1500],
            )
        )
    return result
