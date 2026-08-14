import hashlib
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent

BASE_URL = "https://ternopil.karabas.com/"
SOURCE_NAME = "KARABAS"
JINA_PREFIX = "https://r.jina.ai/"
MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5,
    "червня": 6, "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10,
    "листопада": 11, "грудня": 12,
}
MONTH_SLUGS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
MONTH_PATTERN = "|".join(MONTHS)


def _clean(s: str) -> str:
    return " ".join(s.replace("\xa0", " ").split()).strip()


def _external_id(url: str, title: str, start: datetime) -> str:
    return hashlib.sha256(f"{url}|{title}|{start.isoformat()}".encode()).hexdigest()[:32]


def _id(url: str, title: str, start: datetime) -> str:
    return _external_id(url, title, start)


def _parse_date_time(value: str) -> datetime | None:
    """Parse the date/time formats used by KARABAS month and root pages."""
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


def _parse_start(block: str) -> datetime | None:
    """Parse the event date first, then find the event time anywhere in its block."""
    date_match = re.search(
        rf"\b(\d{{1,2}})\s+(?:[А-Яа-яІіЇїЄєҐґ]+\s+)?({MONTH_PATTERN})\s*[’']?\s*(20\d{{2}})?",
        block,
        re.I,
    )
    if not date_match:
        return None

    day, month, year = date_match.groups()
    year_value = int(year) if year else datetime.now().year
    time_matches = list(re.finditer(r"\b(\d{1,2}):(\d{2})\b", block))
    if not time_matches:
        return None
    time_match = next(
        (m for m in time_matches if m.start() > date_match.end()),
        time_matches[0],
    )
    try:
        return datetime(
            year_value,
            MONTHS[month.lower()],
            int(day),
            int(time_match.group(1)),
            int(time_match.group(2)),
        )
    except ValueError:
        return None


def _price(s: str) -> str | None:
    m = re.search(
        r"\d[\d\s]*(?:-|–)\s*\d[\d\s]*\s*(?:грн|UAH)|\d[\d\s]*\s*(?:грн|UAH)",
        s,
        re.I,
    )
    return _clean(m.group(0)) if m else None


def _is_date_heading(line: str) -> bool:
    return bool(re.search(rf"^\d{{1,2}}\s+.*?({MONTH_PATTERN}).*?20\d{{2}}\s*$", line, re.I))


def _extract_events(text: str, source_url: str, now: datetime) -> list[RawEvent]:
    lines = [_clean(x.strip("#*- ")) for x in text.splitlines() if _clean(x.strip("#*- "))]
    date_indices = [i for i, line in enumerate(lines) if _is_date_heading(line)]
    events: list[RawEvent] = []

    for pos, idx in enumerate(date_indices):
        end = date_indices[pos + 1] if pos + 1 < len(date_indices) else len(lines)
        block_lines = lines[idx:end]
        block = " ".join(block_lines)
        if "Тернопіль" not in block:
            continue
        if re.search(r"\b(Скасовано|Перенесено|Cancelled|Transferred|Продано)\b", block, re.I):
            continue
        start = _parse_start(block)
        if not start or start < now:
            continue

        city_idx = next(
            (j for j, x in enumerate(block_lines)
             if re.search(r"^Тернопіль(?:,|\s|$)", x, re.I)),
            None,
        )
        if city_idx is None:
            continue

        ignored = {"концерти", "театри", "фестивалі", "клуби", "інші"}
        title = next(
            (
                x for x in reversed(block_lines[1:city_idx])
                if len(x) > 2 and x.lower() not in ignored and not _is_date_heading(x)
            ),
            None,
        )
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
    return list({e.external_id: e for e in events}.values())


def _month_urls(now: datetime) -> list[str]:
    """Current month plus five following KARABAS public calendar pages."""
    urls: list[str] = []
    for offset in range(6):
        month_index = now.month - 1 + offset
        slug = MONTH_SLUGS[month_index % 12]
        urls.append(f"{BASE_URL}{slug}/")
    return urls


def _get_page(client: httpx.Client, url: str, timeout: float) -> str:
    """Prefer Jina Reader because KARABAS blocks GitHub Actions with HTTP 403."""
    try:
        response = client.get(JINA_PREFIX + url, timeout=timeout)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError:
        response = client.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text


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
                soup = BeautifulSoup(text, "lxml")
                text = "\n".join(_clean(x) for x in soup.stripped_strings if _clean(x))

            events.extend(_extract_events(text, url, now))

    return list({e.external_id: e for e in events}.values())
