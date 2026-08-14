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


def collect_jsonld(
    url: str,
    source_name: str | None = None,
    timeout: float = 20.0,
) -> list[RawEvent]:
    """Collect Schema.org Event data from a source page.

    Supports Event subtypes such as MusicEvent/TheaterEvent and events nested
    inside @graph, itemListElement, item, and other JSON-LD containers.
    """
    _ = source_name
    response = httpx.get(
        url,
        headers={"User-Agent": "TernopilEventsBot/0.1"},
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    result: list[RawEvent] = []

    def consume(value) -> None:
        if isinstance(value, list):
            for item in value:
                consume(item)
            return
        if not isinstance(value, dict):
            return

        event_type = value.get("@type")
        event_types = event_type if isinstance(event_type, list) else [event_type]
        is_event = any(
            isinstance(item, str)
            and (item == "Event" or item.rsplit("/", 1)[-1].endswith("Event"))
            for item in event_types
        )

        if is_event:
            name = value.get("name")
            start = value.get("startDate")
            if name and start:
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

                result.append(
                    RawEvent(
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
                    )
                )

        # Many sites wrap events in ItemList/ListItem or other containers.
        # Walk all nested JSON-LD values so the collector is not tied to one
        # particular schema layout.
        for key, child in value.items():
            if key.startswith("@") and key not in {"@graph", "@type"}:
                continue
            if key == "@type":
                continue
            consume(child)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        consume(payload)

    unique = {event.external_id: event for event in result}
    return list(unique.values())
