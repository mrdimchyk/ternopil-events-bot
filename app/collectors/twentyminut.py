import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent
from app.collectors.generic_html import _category

BASE_URL = "https://te.20minut.ua/Kult-podii"
SOURCE_NAME = "20 хвилин Тернопіль"
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
    r"^(?P<day>\d{1,2})\s+(?P<month>січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)(?:\s+(?P<year>20\d{2}))?\s*,?\s*(?P<hour>\d{1,2})[:.](?P<minute>\d{2})(?:\s*,?\s*(?P<rest>.*))?$",
    re.I,
)
_SKIP = {
    "концерти",
    "виставки",
    "вистави",
    "майстер-класи",
    "екскурсії",
}


def _id(url: str, start_at: datetime, title: str) -> str:
    return hashlib.sha256(f"{url}|{start_at.isoformat()}|{title}".encode()).hexdigest()[:32]


def _parse_date(line: str, default_year: int) -> tuple[datetime, str | None] | None:
    match = _DATE_RE.match(line.strip())
    if not match:
        return None
    groups = match.groupdict()
    try:
        start_at = datetime(
            int(groups["year"] or default_year),
            _MONTHS[groups["month"].lower()],
            int(groups["day"]),
            int(groups["hour"]),
            int(groups["minute"]),
        )
    except (KeyError, ValueError):
        return None
    rest = (groups.get("rest") or "").strip(" ,") or None
    return start_at, rest


def _is_candidate_title(text: str) -> bool:
    normalized = " ".join(text.split()).strip(" -—:")
    if not normalized or normalized.lower() in _SKIP:
        return False
    if normalized.startswith(
        (
            "У Тернополі",
            "Екскурсії,",
            "Кількість місць",
            "Для запису",
            "Вхід",
            "Цього",
            "Нагадаємо",
            "Учасники",
        )
    ):
        return False
    if re.match(r"^\d{1,2}\s+\S+", normalized):
        return False
    return len(normalized) >= 4


def _title_around_date(lines: list[str], index: int) -> str | None:
    following = lines[index + 1 : index + 4]
    previous = lines[max(0, index - 4) : index]
    next_title = next((candidate for candidate in following if _is_candidate_title(candidate)), None)
    previous_title = next(
        (
            candidate
            for candidate in reversed(previous)
            if _is_candidate_title(candidate) and "тернопіль" not in candidate.lower()
        ),
        None,
    )

    # The observed source uses both layouts: date -> title and title/location -> date.
    # A previous line can be a venue/location; when the next candidate is followed by
    # another date, that next candidate is the event title.
    if next_title is not None:
        next_title_index = lines.index(next_title, index + 1)
        if any(
            _parse_date(candidate, datetime.now().year)
            for candidate in lines[next_title_index + 1 : next_title_index + 3]
        ):
            return next_title
        return next_title
    return previous_title


def _parse_article(html: str, page_url: str, now: datetime) -> list[RawEvent]:
    soup = BeautifulSoup(html, "lxml")
    lines = [" ".join(line.split()) for line in soup.get_text("\n").splitlines() if line.strip()]
    result: list[RawEvent] = []
    seen: set[tuple[str, datetime]] = set()

    for index, line in enumerate(lines):
        parsed = _parse_date(line, now.year)
        if not parsed:
            continue
        start_at, rest = parsed
        if start_at < now:
            continue

        title = _title_around_date(lines, index)
        if title is None:
            continue

        venue = None
        if rest and "тернопіль" in rest.lower():
            venue = rest
        else:
            for candidate in reversed(lines[max(0, index - 2) : index]):
                if "тернопіль" in candidate.lower() and _is_candidate_title(candidate):
                    venue = candidate
                    break

        key = (title, start_at)
        if key in seen:
            continue
        seen.add(key)
        source_url = page_url
        result.append(
            RawEvent(
                external_id=_id(source_url, start_at, title),
                title=title,
                category=_category(title),
                start_at=start_at,
                venue=venue,
                address=None,
                price_text=None,
                ticket_url=source_url,
                source_url=source_url,
                description="Джерело: 20 хвилин Тернопіль",
            )
        )
    return result


def _article_urls(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    result: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        title = " ".join(anchor.stripped_strings)
        href = anchor.get("href")
        if not href or not title:
            continue
        if "Куди піти" not in title and "Афіша" not in title:
            continue
        url = urljoin(page_url, href)
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
        if len(result) >= 3:
            break
    return result


def collect(timeout: float = 20.0) -> list[RawEvent]:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/139 Safari/537.36",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
    }
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        index_response = client.get(BASE_URL)
        index_response.raise_for_status()
        result: list[RawEvent] = []
        for url in _article_urls(index_response.text, str(index_response.url)):
            response = client.get(url)
            response.raise_for_status()
            result.extend(_parse_article(response.text, str(response.url), datetime.now()))
    return result
