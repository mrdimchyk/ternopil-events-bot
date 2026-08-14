import hashlib
import re
from datetime import datetime

import httpx

from app.collectors.base import RawEvent

BASE_URL = "https://ternopil.karabas.com/"
SOURCE_NAME = "KARABAS"
JINA_PREFIX = "https://r.jina.ai/"
MONTH_SLUGS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5,
    "червня": 6, "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10,
    "листопада": 11, "грудня": 12,
}
MONTH_PATTERN = "|".join(MONTHS)


def _clean(s: str) -> str:
    return " ".join(s.replace("\xa0", " ").split()).strip()


def _id(url: str, title: str, start: datetime) -> str:
    return hashlib.sha256(f"{url}|{title}|{start.isoformat()}".encode()).hexdigest()[:32]


def _parse_start(block: str) -> datetime | None:
    date_match = re.search(
        rf"\b(\d{{1,2}})\s+(?:[А-Яа-яІіЇїЄєҐґ]+\s+)?({MONTH_PATTERN})\s*[’']?\s*(20\d{{2}})",
        block,
        re.I,
    )
    if not date_match:
        return None
    day, month, year = date_match.groups()
    time_match = re.search(r"Тернопіль,.*?(\d{1,2}):(\d{2})", block, re.I | re.S)
    if not time_match:
        return None
    try:
        return datetime(int(year), MONTHS[month.lower()], int(day), int(time_match.group(1)), int(time_match.group(2)))
    except ValueError:
        return None


def _price(s: str) -> str | None:
    m = re.search(
        r"\d[\d\s]*(?:-|–)\s*\d[\d\s]*\s*(?:грн|UAH)|\d[\d\s]*\s*(?:грн|UAH)",
        s,
        re.I,
    )
    return _clean(m.group(0)) if m else None


def collect(timeout: float = 30.0):
    now = datetime.now()
    urls = []
    for offset in range(6):
        idx = now.month - 1 + offset
        urls.append(f"{BASE_URL}{MONTH_SLUGS[idx % 12]}/")

    headers = {
        "User-Agent": "TernopilEventsBot/1.0",
        "Accept": "text/plain,text/markdown,text/html;q=0.9,*/*;q=0.8",
    }
    events: dict[str, RawEvent] = {}

    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        for source_url in urls:
            # Direct Karabas requests from GitHub-hosted runners receive 403.
            # Jina Reader fetches the public page and returns rendered text.
            response = client.get(
                JINA_PREFIX + source_url,
                headers={**headers, "x-no-cache": "true"},
            )
            response.raise_for_status()
            text = response.text

            matches = list(re.finditer(
                rf"(?m)^\s*(\d{{1,2}})\s+[^\n]*?({MONTH_PATTERN})\s*[’']?\s*(20\d{{2}})\s*$",
                text,
                re.I,
            ))
            for pos, match in enumerate(matches):
                block = text[match.start():matches[pos + 1].start() if pos + 1 < len(matches) else len(text)]
                if "Тернопіль," not in block:
                    continue
                if re.search(r"\b(Скасовано|Перенесено|Cancelled|Transferred)\b", block, re.I):
                    continue
                start = _parse_start(block)
                if not start or start < now:
                    continue

                lines = [_clean(x.strip("#*- ")) for x in block.splitlines() if _clean(x.strip("#*- "))]
                city_line = next((i for i, x in enumerate(lines) if x.startswith("Тернопіль,")), None)
                if city_line is None:
                    continue
                ignored = {
                    "концерти", "театри", "фестивалі", "клуби", "інші",
                    "concerts", "theatres", "festivals", "clubs", "other",
                }
                title = next((line for line in lines[1:city_line] if line.lower() not in ignored and len(line) > 2), None)
                if not title:
                    continue
                venue = lines[city_line + 1] if city_line + 1 < len(lines) else None
                price = _price(block)
                event = RawEvent(
                    external_id=_id(source_url, title, start),
                    title=title,
                    category="concert" if "концерт" in block.lower() else ("theatre" if "театр" in block.lower() else None),
                    start_at=start,
                    venue=venue,
                    address=None,
                    price_text=price,
                    ticket_url=source_url,
                    source_url=source_url,
                    description=None,
                )
                events[event.external_id] = event

    return list(events.values())
