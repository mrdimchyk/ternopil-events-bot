import hashlib
import json
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent


def _id(url: str, name: str, start: str | None) -> str:
    return hashlib.sha256(f"{url}|{name}|{start}".encode()).hexdigest()[:32]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def collect_jsonld(url: str, timeout: float = 20.0) -> list[RawEvent]:
    response = httpx.get(
        url,
        headers={"User-Agent": "TernopilEventsBot/0.1"},
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    result: list[RawEvent] = []

    def consume(value):
        if isinstance(value, list):
            for item in value:
                consume(item)
            return
        if not isinstance(value, dict):
            return
        if "@graph" in value:
            consume(value["@graph"])
        event_type = value.get("@type")
        is_event = event_type == "Event" or (
            isinstance(event_type, list) and "Event" in event_type
        )
        if not is_event:
            return

        name = value.get("name")
        start = value.get("startDate")
        if not name or not start:
            return

        location = value.get("location") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        venue = location.get("name") if isinstance(location, dict) else None
        address = location.get("address") if isinstance(location, dict) else None
        if isinstance(address, dict):
            address = address.get("streetAddress")

        offers = value.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        ticket_url = offers.get("url") if isinstance(offers, dict) else None
        price = offers.get("price") if isinstance(offers, dict) else None
        price_text = f"{price} грн" if price is not None else None
        source_url = urljoin(url, value.get("url") or url)

        result.append(RawEvent(
            external_id=_id(source_url, str(name), str(start)),
            title=str(name).strip(),
            category=None,
            start_at=_parse_datetime(str(start)),
            venue=venue,
            address=address,
            price_text=price_text,
            ticket_url=ticket_url,
            source_url=source_url,
            description=value.get("description"),
        ))

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            consume(json.loads(script.string or script.get_text()))
        except (json.JSONDecodeError, TypeError):
            continue

    unique = {event.external_id: event for event in result}
    return list(unique.values())
