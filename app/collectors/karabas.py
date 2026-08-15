import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent

BASE_URL = "https://ternopil.karabas.com/"
SOURCE_NAME = "KARABAS"
JINA_PREFIX = "https://r.jina.ai/"
DEBUG_DIR = Path("artifacts/karabas")
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
MONTH_SLUGS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
MONTH_PATTERN = "|".join(MONTHS)
CATEGORY_LABELS = {
    "концерти", "театри", "дітям", "stand-up", "клуби", "фестивалі", "інші",
}
DATE_HEADING_RE = re.compile(
    rf"^\d{{1,2}}\s+.*?({MONTH_PATTERN}).*?20\d{{2}}\s*$", re.I
)
LOCATION_RE = re.compile(
    rf"^Тернопіль,\s*\d{{1,2}}\s+({MONTH_PATTERN})\s+20\d{{2}},\s*\d{{1,2}}:\d{{2}}$", re.I
)
PRICE_RE = re.compile(
    r"^(?:\d[\d\s]*(?:-|–)\s*\d[\d\s]*|\d[\d\s]*)\s*(?:грн|UAH)$", re.I
)
MARKDOWN_LINK_RE = re.compile(r"^\[([^\]]+)\]\(([^)]+)\)$")


def _clean(s: str) -> str:
    return " ".join(s.replace("\xa0", " ").split()).strip()


def _external_id(url: str, title: str, start: datetime) -> str:
    return hashlib.sha256(f"{url}|{title}|{start.isoformat()}".encode()).hexdigest()[:32]


def _id(url: str, title: str, start: datetime) -> str:
    return _external_id(url, title, start)


def _parse_date_time(value: str) -> datetime | None:
    patterns = (
        rf"\b(\d{{1,2}})\s+(?:[А-Яа-яІіЇїЄєҐґ]+\s+)?({MONTH_PATTERN})\s*[’']?\s*(20\d{{2}})\s*,?\s*(\d{{1,2}}):(\d{{2}})",
        rf"\b(\d{{1,2}})\s+(?:[А-Яа-яІіЇїЄєҐґ]+\s+)?({MONTH_PATTERN})\s*,?\s*(\d{{1,2}}):(\d{{2}})",
    )
    for pattern in patterns:
        match = re.search(pattern, value, re.I)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 5:
            day, month, year, hour, minute = groups
        else:
            day, month, hour, minute = groups
            year = str(datetime.now().year)
        try:
            return datetime(int(year), MONTHS[month.lower()], int(day), int(hour), int(minute))
        except ValueError:
            return None
    return None


def _is_date_heading(line: str) -> bool:
    return bool(DATE_HEADING_RE.search(line))


def _is_category_line(line: str) -> bool:
    parts = [_clean(part).lower() for part in line.split("|")]
    return bool(parts) and all(part in CATEGORY_LABELS for part in parts)


def _parse_price_line(line: str) -> str | None:
    return _clean(line) if PRICE_RE.fullmatch(_clean(line)) else None


def _event_blocks(lines: list[str]) -> list[list[str]]:
    date_indices = [i for i, line in enumerate(lines) if _is_date_heading(line)]
    return [
        lines[idx:date_indices[pos + 1] if pos + 1 < len(date_indices) else len(lines)]
        for pos, idx in enumerate(date_indices)
    ]


def _title_and_url(line: str, source_url: str) -> tuple[str, str]:
    match = MARKDOWN_LINK_RE.fullmatch(line.strip())
    if match:
        return _clean(match.group(1)), urljoin(source_url, match.group(2))
    return _clean(line), source_url


def _extract_event_cards(text: str, source_url: str, now: datetime) -> list[RawEvent]:
    """Extract KARABAS event cards from their stable semantic field order."""
    lines = [_clean(x.strip("#*- ")) for x in text.splitlines() if _clean(x.strip("#*- "))]
    events: list[RawEvent] = []

    for block_lines in _event_blocks(lines):
        location_idx = next(
            (i for i, line in enumerate(block_lines) if LOCATION_RE.fullmatch(line)), None
        )
        if location_idx is None or location_idx < 2:
            continue

        start = _parse_date_time(block_lines[location_idx])
        if not start or start < now:
            continue

        title_candidates = [
            line for line in block_lines[1:location_idx] if not _is_category_line(line)
        ]
        if not title_candidates:
            continue
        title, event_url = _title_and_url(title_candidates[-1], source_url)
        if not title:
            continue

        category_line = next(
            (line for line in block_lines[1:location_idx] if _is_category_line(line)), None
        )
        category = None
        if category_line:
            category_lower = category_line.lower()
            if "концерт" in category_lower:
                category = "concert"
            elif "театр" in category_lower:
                category = "theatre"
            elif "stand-up" in category_lower:
                category = "standup"

        venue = block_lines[location_idx + 1] if location_idx + 1 < len(block_lines) else None
        status_or_price = block_lines[location_idx + 2] if location_idx + 2 < len(block_lines) else None
        if status_or_price and re.search(
            r"\b(Скасовано|Перенесено|Cancelled|Transferred|Продано)\b",
            status_or_price,
            re.I,
        ):
            continue
        price_text = _parse_price_line(status_or_price) if status_or_price else None

        events.append(
            RawEvent(
                external_id=_external_id(event_url, title, start),
                title=title,
                category=category,
                start_at=start,
                venue=venue,
                address=None,
                price_text=price_text,
                ticket_url=event_url,
                source_url=event_url,
                description=None,
            )
        )

    return list({e.external_id: e for e in events}.values())


def _extract_events(text: str, source_url: str, now: datetime) -> list[RawEvent]:
    return _extract_event_cards(text, source_url, now)


def _month_urls(now: datetime) -> list[str]:
    return [
        f"{BASE_URL}{MONTH_SLUGS[(now.month - 1 + offset) % 12]}/"
        for offset in range(6)
    ]


def _get_page(client: httpx.Client, url: str, timeout: float) -> str:
    try:
        response = client.get(JINA_PREFIX + url, timeout=timeout)
        response.raise_for_status()
        text = response.text
    except httpx.HTTPError:
        response = client.get(url, timeout=timeout)
        response.raise_for_status()
        text = response.text

    if os.getenv("KARABAS_DEBUG") == "1":
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        slug = url.rstrip("/").split("/")[-1] or "root"
        (DEBUG_DIR / f"{slug}.txt").write_text(text, encoding="utf-8")
    return text


def _html_to_markdownish(text: str, base_url: str) -> str:
    soup = BeautifulSoup(text, "lxml")
    for anchor in soup.select("a[href]"):
        label = _clean(anchor.get_text(" ", strip=True))
        href = anchor.get("href")
        if label and href:
            anchor.replace_with(f"[{label}]({urljoin(base_url, href)})")
    return "\n".join(_clean(x) for x in soup.stripped_strings if _clean(x))


def collect(timeout: float = 30.0):
    now = datetime.now()
    headers = {
        "User-Agent": "TernopilEventsBot/1.0 (+https://github.com/mrdimchyk/ternopil-events-bot)",
        "Accept": "text/plain,text/markdown,text/html;q=0.9,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
    }
    events: list[RawEvent] = []
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        for url in _month_urls(now):
            try:
                text = _get_page(client, url, timeout)
            except httpx.HTTPError:
                continue
            if "<html" in text.lower() or "<body" in text.lower():
                text = _html_to_markdownish(text, url)
            events.extend(_extract_event_cards(text, url, now))
    return list({e.external_id: e for e in events}.values())
