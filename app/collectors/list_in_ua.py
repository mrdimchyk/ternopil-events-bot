import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import RawEvent
from app.collectors.generic_html import _category, _parse_datetime

SOURCE_NAME = "List.in.ua"
BASE_URL = "https://list.in.ua/%D0%A2%D0%B5%D1%80%D0%BD%D0%BE%D0%BF%D1%96%D0%BB%D1%8C/afisha/soon"

_DATE_RE = re.compile(
    r"\b\d{1,2}[./-]\d{1,2}[./-]20\d{2}\s+\d{1,2}:\d{2}\b"
    r"|\b\d{1,2}[./-]\d{1,2}[./-]20\d{2}\b",
    re.I,
)
_PRICE_RE = re.compile(r"(?:від\s*)?\d[\d\s]*(?:[.,]\d+)?\s*(?:₴|грн)", re.I)
_GENERIC_TEXT = {"купити квиток", "купити", "детальніше", "читати далі", "показати більше"}


def _id(url: str, title: str, start_at: datetime | None) -> str:
    value = start_at.isoformat() if start_at else ""
    return hashlib.sha256(f"{url}|{title}|{value}".encode()).hexdigest()[:32]


def collect(timeout: float = 20.0) -> list[RawEvent]:
    """Collect upcoming Ternopil event cards from List.in.ua's public catalog."""
    response = httpx.get(
        BASE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
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
    seen_urls: set[str] = set()

    for anchor in soup.select("a[href*='/afisha/']"):
        href = urljoin(BASE_URL, anchor.get("href", ""))
        if not href.startswith(("http://", "https://")) or href == BASE_URL:
            continue
        anchor_text = " ".join(anchor.stripped_strings).strip()
        block: Tag | None = anchor
        selected: Tag | None = None
        for _ in range(8):
            if not isinstance(block, Tag):
                break
            text = " ".join(block.stripped_strings)
            if _DATE_RE.search(text) and 30 <= len(text) <= 2500:
                selected = block
                break
            block = block.parent
        if selected is None:
            continue

        text = " ".join(selected.stripped_strings)
        match = _DATE_RE.search(text)
        if not match:
            continue
        parse_text = text
        if not re.search(r"\b\d{1,2}[./-]\d{1,2}[./-]20\d{2}\s+\d{1,2}:\d{2}\b", match.group(0)):
            parse_text = f"{match.group(0)} 00:00"
        start_at = _parse_datetime(parse_text, now=now)
        if not start_at or href in seen_urls:
            continue

        title = anchor_text
        if not title or title.lower() in _GENERIC_TEXT:
            for tag in selected.select("h1, h2, h3, h4, h5, [class*='title'], [class*='name']"):
                candidate = " ".join(tag.stripped_strings).strip()
                if candidate and candidate.lower() not in _GENERIC_TEXT:
                    title = candidate
                    break
        if not title or title.lower() in _GENERIC_TEXT:
            continue

        price_match = _PRICE_RE.search(text)
        price_text = price_match.group(0).strip() if price_match else None
        venue = None
        for candidate in selected.select("a[href]"):
            candidate_href = urljoin(BASE_URL, candidate.get("href", ""))
            candidate_text = " ".join(candidate.stripped_strings).strip()
            if candidate_href == href or not candidate_text or candidate_text.lower() in _GENERIC_TEXT:
                continue
            if "/afisha/" not in candidate_href:
                venue = candidate_text
                break
        if venue is None:
            low = text.lower()
            for marker in ("місце проведення:", "тернопіль"):
                idx = low.find(marker)
                if idx >= 0:
                    tail = text[idx + len(marker):].strip(" :,-|•—–")
                    venue = re.split(r"\s+(?:вхід|початок|вартість|квитки|для того|зацікавила)\b", tail, maxsplit=1, flags=re.I)[0].strip()
                    if venue:
                        break

        result.append(
            RawEvent(
                external_id=_id(href, title, start_at),
                title=title,
                category=_category(text),
                start_at=start_at,
                venue=venue or None,
                address=None,
                price_text=price_text,
                ticket_url=href,
                source_url=href,
                description=None,
            )
        )
        seen_urls.add(href)

    return result
