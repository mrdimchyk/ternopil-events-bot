import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent

MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}
MONTH_RE = "|".join(MONTHS)
DATE_RE = re.compile(rf"^(\d{{1,2}})\s+({MONTH_RE})\s+(\d{{1,2}}):(\d{{2}})\b", re.I)


def _clean(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _event_id(url: str, title: str, start: datetime) -> str:
    return hashlib.sha256(f"{url}|{title}|{start.isoformat()}".encode()).hexdigest()[:32]


def _parse_date(line: str, year: int) -> datetime | None:
    m = DATE_RE.match(_clean(line).lower())
    if not m:
        return None
    day, month, hour, minute = m.groups()
    try:
        return datetime(year, MONTHS[month], int(day), int(hour), int(minute))
    except ValueError:
        return None


def _price(text: str) -> str | None:
    m = re.search(r"\d[\d\s]*(?:-|–)\s*\d[\d\s]*\s*грн|\d[\d\s]*\s*грн|від\s*\d[\d\s]*\s*(?:₴|грн)", text, re.I)
    return _clean(m.group(0)) if m else None


def _category(lines: list[str]) -> str | None:
    text = " ".join(lines).lower()
    if "стендап" in text or "stand-up" in text:
        return "standup"
    if "фестив" in text:
        return "festival"
    if "театр" in text or "вистав" in text:
        return "theatre"
    if "концерт" in text:
        return "concert"
    if "цирк" in text:
        return "circus"
    if "дит" in text:
        return "children"
    return None


def collect_line_catalog(urls: list[str], timeout: float = 20.0) -> list[RawEvent]:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
    }
    now = datetime.now()
    events: dict[str, RawEvent] = {}

    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        for page_url in urls:
            response = client.get(page_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            lines = [_clean(x) for x in soup.stripped_strings if _clean(x)]
            page_text = " ".join(lines)
            year_match = re.search(r"\b20\d{2}\b", page_text)
            year = int(year_match.group()) if year_match else now.year

            for i, line in enumerate(lines):
                start = _parse_date(line, year)
                if not start or start < now:
                    continue

                # The source layout is: date/time -> type tags -> title -> city -> venue -> price/status.
                window = lines[i + 1:i + 12]
                city_index = next((j for j, x in enumerate(window) if x.startswith("Тернопіль")), None)
                if city_index is None:
                    continue
                before_city = window[:city_index]
                title = next((x for x in reversed(before_city) if len(x) > 2 and x.lower() not in {"театр", "концерт", "спорт", "клуб", "цирк", "дітям", "балет", "розваги", "відпочинок"}), None)
                if not title:
                    continue
                after_city = window[city_index + 1:]
                if after_city and after_city[0] == "•":
                    after_city = after_city[1:]
                venue = after_city[0] if after_city else None
                joined = " ".join(window)
                if re.search(r"ПОДІЯ\s+(ЗАКІНЧИЛАСЬ|ЗАКІНЧИЛАСЯ)|EVENT\s+ENDED", joined, re.I):
                    continue
                price = _price(joined)
                href = None
                for a in soup.select("a[href]"):
                    if _clean(a.get_text(" ", strip=True)) == title:
                        href = urljoin(page_url, a.get("href"))
                        break
                source_url = href or page_url
                event = RawEvent(
                    external_id=_event_id(source_url, title, start),
                    title=title,
                    category=_category(window),
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
