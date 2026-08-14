import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent

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
UA_MONTH_RE = "|".join(MONTHS)


def _clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _event_id(url: str, title: str, start_at: datetime | None) -> str:
    raw = f"{url}|{title}|{start_at.isoformat() if start_at else ''}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _parse_datetime(text: str, default_year: int | None = None) -> datetime | None:
    text = _clean(text).lower().replace("’", "'")

    m = re.search(
        rf"(\d{{1,2}})\s+(?:[а-яіїєґ]+\s+)?({UA_MONTH_RE})\s*(?:['’]\s*)?(20\d{{2}})?[^0-9]{{0,12}}(\d{{1,2}}):(\d{{2}})",
        text,
    )
    if m:
        day, month_name, year, hour, minute = m.groups()
        year = int(year) if year else (default_year or datetime.now().year)
        return datetime(year, MONTHS[month_name], int(day), int(hour), int(minute))

    # TicketsBox: 17 вересня 19:00 вівторок
    m = re.search(rf"(\d{{1,2}})\s+({UA_MONTH_RE})\s+(\d{{1,2}}):(\d{{2}})", text)
    if m:
        day, month_name, hour, minute = m.groups()
        year = default_year or datetime.now().year
        return datetime(year, MONTHS[month_name], int(day), int(hour), int(minute))

    return None


def _price(text: str) -> str | None:
    m = re.search(
        r"(\d[\d\s]*)\s*(?:-|–)\s*(\d[\d\s]*)\s*грн|([\d\s]+)\s*грн|від\s*([\d\s]+)\s*(?:₴|грн)",
        text,
        re.I,
    )
    return _clean(m.group(0)) if m else None


def _category(text: str) -> str | None:
    low = text.lower()
    if "стендап" in low or "stand-up" in low or "stand up" in low:
        return "standup"
    if "фестив" in low:
        return "festival"
    if "театр" in low or "вистав" in low:
        return "theatre"
    if "концерт" in low or "concert" in low:
        return "concert"
    if "цирк" in low:
        return "circus"
    if "дит" in low:
        return "children"
    return None


def _is_action(text: str) -> bool:
    return _clean(text).lower() in {
        "купити", "купить", "buy", "квитки", "квиток",
        "детальніше", "подробнее", "more",
    }


def _nearest_block(link):
    node = link
    for _ in range(8):
        if not node.parent:
            break
        node = node.parent
        if getattr(node, "name", None) in {"article", "li"}:
            return node
        classes = " ".join(node.get("class", [])) if hasattr(node, "get") else ""
        if re.search(r"event|card|item|ticket|afisha|poster|listing|catalog", classes, re.I):
            return node
    return link.parent or link


def _title(block, link) -> str | None:
    for tag in block.select("h1,h2,h3,h4,h5,.title,.name"):
        value = _clean(tag.get_text(" ", strip=True))
        if value and not _is_action(value) and len(value) > 2:
            return value
    candidates = []
    for a in block.select("a[href]"):
        value = _clean(a.get_text(" ", strip=True))
        if value and not _is_action(value) and len(value) > 2:
            candidates.append(value)
    if candidates:
        return max(candidates, key=len)
    value = _clean(link.get_text(" ", strip=True))
    return value if value and not _is_action(value) else None


def _event_url(block, base_url: str, fallback_link) -> str:
    for link in block.select("a[href]"):
        text = _clean(link.get_text(" ", strip=True))
        href = link.get("href")
        if href and text and not _is_action(text):
            return urljoin(base_url, href)
    return urljoin(base_url, fallback_link.get("href", base_url))


def _venue(text: str, start_at: datetime | None, price_text: str | None) -> str | None:
    # TicketsBox format: "Тернопіль • Venue"
    m = re.search(r"Терноп(?:і|о)ль\s*[•·]\s*(.+)", text, re.I)
    if m:
        tail = m.group(1)
        if price_text:
            pos = tail.lower().find(price_text.lower())
            if pos >= 0:
                tail = tail[:pos]
        tail = re.split(r"\b(Продано|Скасовано|Перенесено|EVENT ENDED|Sold out|Cancelled|Postponed)\b", tail, flags=re.I)[0]
        return _clean(tail).strip("•|,–-") or None

    # Karabas / Teatr format: "Тернопіль, ... HH:MM Venue ... price"
    tail = text
    if start_at:
        marker = f"{start_at.hour}:{start_at.minute:02d}"
        pos = tail.find(marker)
        if pos >= 0:
            tail = tail[pos + len(marker):]
    if price_text:
        pos = tail.lower().find(price_text.lower())
        if pos >= 0:
            tail = tail[:pos]
    tail = re.split(r"\b(Продано|Скасовано|Перенесено|EVENT ENDED|Sold out|Cancelled|Postponed)\b", tail, flags=re.I)[0]
    tail = re.sub(r"\b(КУПИТИ|КУПИТЬ|BUY|Детальніше|Подробнее)\b", "", tail, flags=re.I)
    return _clean(tail).strip("•|,–-") or None


def _cancelled(text: str) -> bool:
    return bool(re.search(r"\b(скасовано|перенесено|cancelled|postponed)\b", text, re.I))


def collect_html(urls: list[str], timeout: float = 20.0, min_future: bool = True) -> list[RawEvent]:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
        "Cache-Control": "no-cache",
    }
    result: list[RawEvent] = []
    now = datetime.now()

    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        for url in urls:
            response = client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            page_text = _clean(soup.get_text(" ", strip=True))
            year_match = re.search(r"\b(20\d{2})\b", page_text)
            default_year = int(year_match.group(1)) if year_match else now.year

            seen_blocks: set[int] = set()
            for link in soup.select("a[href]"):
                block = _nearest_block(link)
                marker = id(block)
                if marker in seen_blocks:
                    continue
                seen_blocks.add(marker)

                text = _clean(block.get_text(" ", strip=True))
                if "Тернопіль" not in text and "Тернополь" not in text:
                    continue
                if _cancelled(text):
                    continue
                start_at = _parse_datetime(text, default_year=default_year)
                if not start_at or (min_future and start_at < now):
                    continue

                title = _title(block, link)
                if not title:
                    continue
                price_text = _price(text)
                source_url = _event_url(block, url, link)
                result.append(RawEvent(
                    external_id=_event_id(source_url, title, start_at),
                    title=title,
                    category=_category(text),
                    start_at=start_at,
                    venue=_venue(text, start_at, price_text),
                    address=None,
                    price_text=price_text,
                    ticket_url=source_url,
                    source_url=source_url,
                    description=None,
                ))

    return list({event.external_id: event for event in result}.values())
