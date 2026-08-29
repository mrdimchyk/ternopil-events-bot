from datetime import datetime

from app.collectors.kasa import _parse_venue_page, _venue_urls


CITY_HTML = """
<html><body>
<h2>Події у Тернопіль</h2>
<h2>Майданчики Тернопіль</h2>
<a href="/philharmonia-t1">Тернопільська обласна філармонія</a>
<a href="/berezil-t2">Палац культури «Березіль»</a>
<h2>Квитки у Тернопіль</h2>
</body></html>
"""

VENUE_HTML = """
<html><body>
<h1>Купити квитки в «Тернопільська обласна філармонія» (Тернопіль) онлайн 2026</h1>
<div>
  <a href="/event/music_123">«Музика великого екрану»</a>
  <div>Тернопільська обласна філармонія</div>
  <div>Середа 2026/09/09</div>
  <div>Час початку 18:30</div>
  <div>Ціна від 200 грн</div>
  <a href="/event/music_123">Придбати квиток</a>
</div>
<div>
  <a href="/event/old_1">Стара подія</a>
  <div>Тернопільська обласна філармонія</div>
  <div>Понеділок 2026.05.25</div>
  <div>Время начала 18:30</div>
</div>
</body></html>
"""


def test_kasa_city_page_exposes_venue_catalog_links():
    assert _venue_urls(CITY_HTML) == [
        "https://kasa.com.ua/philharmonia-t1",
        "https://kasa.com.ua/berezil-t2",
    ]


def test_kasa_parses_future_event_and_ignores_old_format():
    events = _parse_venue_page(
        VENUE_HTML,
        "https://kasa.com.ua/philharmonia-t1",
        datetime(2026, 8, 29, 9, 0),
    )
    assert len(events) == 1
    event = events[0]
    assert event.title == "Музика великого екрану"
    assert event.start_at == datetime(2026, 9, 9, 18, 30)
    assert event.price_text == "Ціна від 200 грн"
    assert event.ticket_url == "https://kasa.com.ua/event/music_123"
    assert event.external_id
