from datetime import datetime
import hashlib
import json
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import RawEvent
from app.collectors.line_catalog import _parse_lines, collect_line_catalog

SOURCE_NAME = "Teatr.org.ua"
BASE_URL = "https://teatr.org.ua/cities/ternopil"
HOME_URL = "https://teatr.org.ua/"
EVENT_PATH_PREFIX = "/events/"
TOUR_PATH_PREFIX = "/tours/"


def _path_urls(text: str, base_url: str, path_prefix: str) -> list[str]:
    soup = BeautifulSoup(text, "lxml")
    candidates: list[str] = []
    candidates.extend(
        anchor.get("href")
        for anchor in soup.select(f'a[href*="{path_prefix}"]')
        if isinstance(anchor.get("href"), str)
    )
    escaped = re.escape(path_prefix)
    candidates.extend(
        re.findall(rf"https?://teatr\\.org\\.ua{escaped}[A-Za-z0-9_./%?=&-]+", text)
    )
    candidates.extend(
        re.findall(rf"(?:https?://teatr\\.org\\.ua)?{escaped}[A-Za-z0-9_./%?=&-]+", text)
    )

    urls: list[str] = []
    seen: set[str] = set()
    for href in candidates:
        url = urljoin(base_url, href).rstrip(")],.;")
        if path_prefix not in url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _event_urls(html: str, base_url: str) -> list[str]:
    return _path_urls(html, base_url, EVENT_PATH_PREFIX)


def _tour_urls(html: str, base_url: str) -> list[str]:
    return _path_urls(html, base_url, TOUR_PATH_PREFIX)


def _raw_jsonld(text: str, page_url: str) -> list[RawEvent]:
    soup = BeautifulSoup(text, "lxml")
    result: dict[str, RawEvent] = {}

    def walk(value) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return

        types = value.get("@type")
        types = types if isinstance(types, list) else [types]
        is_event = any(
            isinstance(t, str)
            and (t == "Event" or t.rsplit("/", 1)[-1].endswith("Event"))
            for t in types
        )
        name = value.get("name")
        start = value.get("startDate")
        if is_event and name and start:
            try:
                start_at = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
            except ValueError:
                start_at = None
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
            source_url = urljoin(page_url, value.get("url") or page_url)
            external_id = hashlib.sha256(f"{source_url}|{name}|{start}".encode()).hexdigest()[:32]
            result[external_id] = RawEvent(
                external_id=external_id,
                title=str(name).strip(),
                category=None,
                start_at=start_at,
                venue=venue,
                address=address,
                price_text=f"{price} грн" if price is not None else None,
                ticket_url=ticket_url,
                source_url=source_url,
                description=value.get("description"),
            )

        for key, child in value.items():
            if key == "@type":
                continue
            if key.startswith("@") and key != "@graph":
                continue
            walk(child)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            walk(json.loads(script.string or script.get_text()))
        except (json.JSONDecodeError, TypeError):
            continue
    return list(result.values())


def _parse_event_page(text: str, page_url: str, now: datetime) -> list:
    soup = BeautifulSoup(text, "lxml")
    lines = [" ".join(x.split()) for x in soup.stripped_strings if " ".join(x.split())]
    if not lines:
        lines = [
            " ".join(x.strip("#*- ").split())
            for x in text.splitlines()
            if " ".join(x.strip("#*- ").split())
        ]
    return _parse_lines(lines, page_url, now.year, now)


def _fetch_markdown(client: httpx.Client, url: str, headers: dict[str, str]) -> str:
    response = client.get(
        "https://r.jina.ai/" + url,
        headers={**headers, "x-no-cache": "true"},
    )
    response.raise_for_status()
    return response.text


def collect(timeout: float = 20.0):
    events = collect_line_catalog([BASE_URL], timeout=timeout)
    if events:
        return events

    now = datetime.now()
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
    }
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        response = client.get(BASE_URL)
        response.raise_for_status()
        urls = _event_urls(response.text, BASE_URL)

        # The city page is dynamically rendered and may expose no event links to
        # ordinary HTTP clients. Discover tours from the home page, then follow
        # their event links; tour pages are server-rendered and stable.
        if not urls:
            pages_to_scan = [HOME_URL]
            for page_url in pages_to_scan:
                try:
                    page = client.get(page_url)
                    page.raise_for_status()
                    tour_urls = _tour_urls(page.text, page_url)
                    if not tour_urls:
                        markdown = _fetch_markdown(client, page_url, headers)
                        tour_urls = _tour_urls(markdown, page_url)
                    for tour_url in tour_urls[:50]:
                        try:
                            tour_page = client.get(tour_url)
                            tour_page.raise_for_status()
                            urls.extend(_event_urls(tour_page.text, tour_url))
                            if not _event_urls(tour_page.text, tour_url):
                                markdown = _fetch_markdown(client, tour_url, headers)
                                urls.extend(_event_urls(markdown, tour_url))
                        except (httpx.HTTPError, ValueError):
                            continue
                except (httpx.HTTPError, ValueError):
                    continue

        # Last resort: ask Jina for the city page itself. It can expose event
        # links even when the origin response is blocked or JS-only.
        if not urls:
            try:
                markdown = _fetch_markdown(client, BASE_URL, headers)
                urls = _event_urls(markdown, BASE_URL)
            except (httpx.HTTPError, ValueError):
                urls = []

        recovered: dict[str, RawEvent] = {}
        for event_url in urls[:100]:
            try:
                page = client.get(event_url)
                page.raise_for_status()
                parsed = [
                    e for e in _raw_jsonld(page.text, event_url)
                    if e.start_at is not None and e.start_at >= now
                ]
                if not parsed:
                    parsed = _parse_event_page(page.text, event_url, now)
                if not parsed:
                    markdown = _fetch_markdown(client, event_url, headers)
                    parsed = [
                        e for e in _raw_jsonld(markdown, event_url)
                        if e.start_at is not None and e.start_at >= now
                    ]
                    if not parsed:
                        parsed = _parse_event_page(markdown, event_url, now)
            except (httpx.HTTPError, ValueError, TypeError):
                continue
            for event in parsed:
                recovered[event.external_id] = event
        return list(recovered.values())
