from datetime import datetime
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.collectors.generic_jsonld import collect_jsonld
from app.collectors.line_catalog import _parse_lines, collect_line_catalog

SOURCE_NAME = "Teatr.org.ua"
BASE_URL = "https://teatr.org.ua/cities/ternopil"
EVENT_PATH_PREFIX = "/events/"


def _event_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    candidates: list[str] = []
    candidates.extend(
        anchor.get("href")
        for anchor in soup.select('a[href*="/events/"]')
        if isinstance(anchor.get("href"), str)
    )
    candidates.extend(re.findall(r"https://teatr\.org\.ua/events/[A-Za-z0-9_./%-]+", html))

    urls: list[str] = []
    seen: set[str] = set()
    for href in candidates:
        url = urljoin(base_url, href).rstrip(")],.;")
        if EVENT_PATH_PREFIX not in url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _parse_event_page(text: str, page_url: str, now: datetime) -> list:
    soup = BeautifulSoup(text, "lxml")
    lines = [" ".join(x.split()) for x in soup.stripped_strings if " ".join(x.split())]
    if not lines:
        lines = [" ".join(x.strip("#*- ").split()) for x in text.splitlines() if " ".join(x.strip("#*- ").split())]
    return _parse_lines(lines, page_url, now.year, now)


def collect(timeout: float = 20.0):
    try:
        structured = collect_jsonld(BASE_URL, SOURCE_NAME, timeout=timeout)
        structured = [event for event in structured if event.start_at is not None and event.start_at >= datetime.now()]
        if structured:
            return structured
    except (httpx.HTTPError, ValueError):
        pass

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
        if not urls:
            jina = client.get("https://r.jina.ai/" + BASE_URL, headers={**headers, "x-no-cache": "true"})
            jina.raise_for_status()
            urls = _event_urls(jina.text, BASE_URL)

        recovered: dict[str, object] = {}
        for event_url in urls[:50]:
            try:
                parsed = collect_jsonld(event_url, SOURCE_NAME, timeout=timeout)
                parsed = [event for event in parsed if event.start_at is not None and event.start_at >= now]
                if not parsed:
                    page = client.get(event_url)
                    page.raise_for_status()
                    parsed = _parse_event_page(page.text, event_url, now)
                    if not parsed:
                        jina = client.get("https://r.jina.ai/" + event_url, headers={**headers, "x-no-cache": "true"})
                        jina.raise_for_status()
                        parsed = _parse_event_page(jina.text, event_url, now)
            except (httpx.HTTPError, ValueError):
                continue
            for event in parsed:
                recovered[event.external_id] = event
        return list(recovered.values())
