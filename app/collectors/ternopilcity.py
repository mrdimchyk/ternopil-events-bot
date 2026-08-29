import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent
from app.collectors.generic_html import _category

SOURCE_NAME = "Ternopil City Council"
BASE_URL = "https://ternopilcity.gov.ua/"

_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{4})\s+"
    r"(?P<hour>\d{1,2})[.:](?P<minute>\d{2})"
)


def _id(source_url: str, title: str, start_at: datetime) -> str:
    value = f"{source_url}|{title}|{start_at.isoformat()}"
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def _parse_start(text: str) -> datetime | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    return datetime(
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
        int(match.group("hour")),
        int(match.group("minute")),
    )


def _extract_rows(page_url: str, html: str) -> list[RawEvent]:
    soup = BeautifulSoup(html, "lxml")
    result: list[RawEvent] = []
    seen: set[str] = set()

    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        values = [" ".join(cell.stripped_strings).strip() for cell in cells]
        title = values[1] if len(values) > 1 else values[0]
        if not title or title.lower() in {"зміст заходу", "термін виконання"}:
            continue
        start_at = _parse_start(" ".join(values))
        if start_at is None:
            continue

        venue = values[3] if len(values) > 3 else None
        source_url = page_url
        event = RawEvent(
            external_id=_id(source_url, title, start_at),
            title=title,
            category=_category(title),
            start_at=start_at,
            venue=venue,
            address=venue,
            price_text=None,
            ticket_url=None,
            source_url=source_url,
            description=" ".join(values[1:]),
        )
        if event.external_id not in seen:
            seen.add(event.external_id)
            result.append(event)

    return result


def _find_latest_plan(home_url: str, html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    candidates: list[tuple[int, str]] = []
    for anchor in soup.find_all("a", href=True):
        text = " ".join(anchor.stripped_strings).strip()
        if "Зведений робочий план" not in text:
            continue
        href = urljoin(home_url, anchor["href"])
        match = re.search(r"/(\d+)\.html$", href)
        if match:
            candidates.append((int(match.group(1)), href))
    if not candidates:
        return None
    return max(candidates)[1]


def collect(timeout: float = 20.0) -> list[RawEvent]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "Chrome/131.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
    }
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        home = client.get(BASE_URL)
        home.raise_for_status()
        plan_url = _find_latest_plan(BASE_URL, home.text)
        if not plan_url:
            return []
        plan = client.get(plan_url)
        plan.raise_for_status()
        return _extract_rows(plan_url, plan.text)
