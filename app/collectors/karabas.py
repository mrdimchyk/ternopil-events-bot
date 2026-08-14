import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx

from app.collectors.base import RawEvent

BASE_URL = "https://ternopil.karabas.com/"
JINA_PREFIX = "https://r.jina.ai/"
_MONTH_SLUGS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5,
    "червня": 6, "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10,
    "листопада": 11, "грудня": 12,
}


def _clean(s: str) -> str:
    return " ".join(s.replace("\xa0", " ").split()).strip()


def _id(url: str, title: str, start: datetime) -> str:
    return hashlib.sha256(f"{url}|{title}|{start.isoformat()}".encode()).hexdigest()[:32]


def _parse_start(s: str) -> datetime | None:
    # Markdown returned by Jina preserves the Karabas visible text:
    # "19 Ср серпня ’ 2026" followed later by "Тернопіль, ... 18:00".
    m = re.search(
        rf"\b(\d{{1,2}})\s+(?:[А-Яа-яІіЇїЄєҐґ]+\s+)?({"|".join(MONTHS)})\s*[’']?\s*(20\d{{2}}).*?Тернопіль,\s*\d{{1,2}}\s+{re.escape('серпня')}|",
        s,
        re.I,
    )
    # Use the simpler two-part parser below; the first expression is only a guard.
    m = re.search(
        rf"\b(\d{{1,2}})\s+(?:[А-Яа-яІіЇїЄєҐґ]+\s+)?({"|".join(MONTHS)})\s*[’']?\s*(20\d{{2}})",
        s,
        re.I,
    )
    if not m:
        return None
    day, month, year = m.groups()
    time = re.search(r"Тернопіль,\s*\d{1,2}\s+[^,]+,\s*(\d{1,2}):(\d{2})", s, re.I)
    if not time:
        time = re.search(r"Тернопіль,\s*\d{1,2}\s+[^,]+\s+\d{4},\s*(\d{1,2}):(\d{2})", s, re.I)
    if not time:
        time = re.search(r"Тернопіль,.*?(\d{1,2}):(\d{2})", s, re.I)
    if not time:
        return None
    try:
        return datetime(int(year), MONTHS[month.lower()], int(day), int(time.group(1)), int(time.group(2)))
    except ValueError:
        return None


def _price(s: str) -> str | None:
    m = re.search(r"\d[\d\s]*(?:-|–)\s*\d[\d\s]*\s*(?:грн|UAH)|\d[\d\s]*\s*(?:грн|UAH)", s, re.I)
    return _clean(m.group(0)) if m else None


def collect(timeout: float = 30.0):
    now = datetime.now()
    urls = []
    for offset in range(6):
        idx = now.month - 1 + offset
        urls.append(f"{BASE_URL}{_MONTH_SLUGS[idx % 12]}/")

    headers = {
        "User-Agent": "TernopilEventsBot/1.0",
        "Accept": "text/plain,text/markdown,text/html;q=0.9,*/*;q=0.8",
    }
    events: dict[str, RawEvent] = {}

    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        for source_url in urls:
            # Direct Karabas requests from GitHub-hosted runners receive 403.
            # Jina Reader fetches the public page and returns its rendered text.
            response = client.get(JINA_PREFIX + source_url, headers={**headers, "x-no-cache": "true"})
            response.raise_for_status()
            text = response.text

            # Split on the date headings used by Karabas. Each block contains
            # title/category/location/price for one event.
            matches = list(re.finditer(
                rf"(?m)^\s*(\d{{1,2}})\s+[^\n]*?({"|".join(MONTHS)})\s*[’']?\s*(20\d{{2}})\s*$",
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
                title = None
                for line in lines[1:city_line]:
                    low = line.lower()
                    if line and low not in {"концерти", "театри", "фестивалі", "фестивали", "клуби", "інші", "other", "concerts", "theatres"}:
                        title = line
                        break
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
