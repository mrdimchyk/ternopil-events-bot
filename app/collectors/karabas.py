import hashlib
import re
from datetime import datetime

import httpx

from app.collectors.base import RawEvent

BASE_URL = "https://ternopil.karabas.com/"
SOURCE_NAME = "KARABAS"
JINA_PREFIX = "https://r.jina.ai/"
MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5,
    "червня": 6, "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10,
    "листопада": 11, "грудня": 12,
}
MONTH_PATTERN = "|".join(MONTHS)


def _clean(s: str) -> str:
    return " ".join(s.replace("\xa0", " ").split()).strip()


def _external_id(url: str, title: str, start: datetime) -> str:
    return hashlib.sha256(f"{url}|{title}|{start.isoformat()}".encode()).hexdigest()[:32]


def _id(url: str, title: str, start: datetime) -> str:
    return _external_id(url, title, start)


def _parse_date_time(value: str) -> datetime | None:
    match = re.search(
        rf"\b(\d{{1,2}})\s+(?:[А-Яа-яІіЇїЄєҐґ]+\s+)?({MONTH_PATTERN})\s*[’']?\s*(20\d{{2}})\s*,?\s*(\d{{1,2}}):(\d{{2}})",
        value,
        re.I,
    )
    if not match:
        return None
    day, month, year, hour, minute = match.groups()
    try:
        return datetime(int(year), MONTHS[month.lower()], int(day), int(hour), int(minute))
    except ValueError:
        return None


def _parse_start(block: str) -> datetime | None:
    return _parse_date_time(block)


def _price(s: str) -> str | None:
    m = re.search(r"\d[\d\s]*(?:-|–)\s*\d[\d\s]*\s*(?:грн|UAH)|\d[\d\s]*\s*(?:грн|UAH)", s, re.I)
    return _clean(m.group(0)) if m else None


def _extract_events(text: str, source_url: str, now: datetime) -> list[RawEvent]:
    lines = [_clean(x.strip("#*- ")) for x in text.splitlines() if _clean(x.strip("#*- "))]
    date_indices = [i for i, line in enumerate(lines) if _parse_date_time(line)]
    events: list[RawEvent] = []

    for pos, idx in enumerate(date_indices):
        start = _parse_date_time(lines[idx])
        if not start or start < now:
            continue
        end = date_indices[pos + 1] if pos + 1 < len(date_indices) else len(lines)
        block_lines = lines[idx:end]
        block = " ".join(block_lines)
        if "Тернопіль" not in block:
            continue
        if re.search(r"\b(Скасовано|Перенесено|Cancelled|Transferred|Продано)\b", block, re.I):
            continue
        city_idx = next((j for j, x in enumerate(block_lines) if re.search(r"^Тернопіль(?:,|\s|$)", x, re.I)), None)
        if city_idx is None:
            continue
        title = next((x for x in reversed(block_lines[1:city_idx]) if len(x) > 2 and x.lower() not in {"концерти", "театри", "фестивалі", "клуби", "інші"}), None)
        if not title:
            continue
        venue = block_lines[city_idx + 1] if city_idx + 1 < len(block_lines) else None
        events.append(RawEvent(
            external_id=_external_id(source_url, title, start),
            title=title,
            category="concert" if "концерт" in block.lower() else ("theatre" if "театр" in block.lower() else None),
            start_at=start,
            venue=venue,
            address=None,
            price_text=_price(block),
            ticket_url=source_url,
            source_url=source_url,
            description=None,
        ))
    return events


def collect(timeout: float = 30.0):
    now = datetime.now()
    headers = {
        "User-Agent": "TernopilEventsBot/1.0",
        "Accept": "text/plain,text/markdown,text/html;q=0.9,*/*;q=0.8",
    }
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        response = client.get(JINA_PREFIX + BASE_URL, headers={**headers, "x-no-cache": "true"})
        response.raise_for_status()
        return _extract_events(response.text, BASE_URL, now)
