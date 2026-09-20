from datetime import datetime
from types import SimpleNamespace

from app.collectors import ticket_kiev


BASE_HTML = '''
<html><body>
  <nav>
    <a href="/ternopil/concert/">Концерт</a>
    <a href="/ternopil/theater/">Театр</a>
    <a href="/ternopil/stand-up/">Стендап</a>
    <a href="/ternopil/children/">Дітям</a>
  </nav>
  <div class="event-card">
    <a href="/cheev-ternopil/">
      <h3>CHEEV</h3>
    </a>
    <div>Концерт 25 жовтня 2026 19:00 Тернопіль Палац культури "Березіль" ім. Леся Курбаса від 350₴</div>
  </div>
</body></html>
'''

CONCERT_HTML = '''
<html><body>
  <div class="event-card">
    <a href="/cheev-ternopil/"><h3>CHEEV</h3></a>
    <div>Концерт 25 жовтня 2026 19:00 Тернопіль Палац культури "Березіль" ім. Леся Курбаса від 350₴</div>
  </div>
  <div class="event-card">
    <a href="/volkanov-ternopil/"><h3>Volkanov</h3></a>
    <div>Концерт 22 вересня 2026 18:00 Тернопіль Палац культури "Березіль" ім. Леся Курбаса від 500₴</div>
  </div>
  <div class="event-card">
    <a href="/past-ternopil/"><h3>Минула подія</h3></a>
    <div>Концерт 18 вересня 2026 18:00 Тернопіль Палац культури "Березіль" ім. Леся Курбаса від 300₴</div>
  </div>
</body></html>
'''

THEATER_HTML = '''
<html><body>
  <div class="event-card">
    <a href="/night-lisbon-ternopil/"><h3>Ніч у Лісабоні</h3></a>
    <div>Театр 26 жовтня 2026 18:00 Тернопіль Театр ім. Шевченка від 300₴</div>
  </div>
</body></html>
'''

EMPTY_HTML = "<html><body></body></html>"


def _response(text: str):
    return SimpleNamespace(text=text, raise_for_status=lambda: None)


def test_ticket_kiev_contract_points_to_ternopil_catalog():
    assert ticket_kiev.SOURCE_NAME == "Ticket.kiev.ua"
    assert ticket_kiev.BASE_URL == "https://ticket.kiev.ua/ternopil/"


def test_ticket_kiev_discovers_existing_category_catalogs():
    assert ticket_kiev._category_urls(BASE_HTML) == [
        "https://ticket.kiev.ua/ternopil/children/",
        "https://ticket.kiev.ua/ternopil/concert/",
        "https://ticket.kiev.ua/ternopil/stand-up/",
        "https://ticket.kiev.ua/ternopil/theater/",
    ]


def test_ticket_kiev_collects_categories_deduplicates_and_skips_past(monkeypatch):
    pages = {
        ticket_kiev.BASE_URL: BASE_HTML,
        "https://ticket.kiev.ua/ternopil/concert/": CONCERT_HTML,
        "https://ticket.kiev.ua/ternopil/theater/": THEATER_HTML,
        "https://ticket.kiev.ua/ternopil/stand-up/": EMPTY_HTML,
        "https://ticket.kiev.ua/ternopil/children/": EMPTY_HTML,
    }
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _response(pages[url])

    monkeypatch.setattr(ticket_kiev.httpx, "get", fake_get)

    result = ticket_kiev.collect(
        timeout=7.5,
        now=datetime(2026, 9, 20, 12, 0),
    )

    assert [event.title for event in result] == [
        "CHEEV",
        "Volkanov",
        "Ніч у Лісабоні",
    ]
    cheev = result[0]
    assert cheev.start_at == datetime(2026, 10, 25, 19, 0)
    assert cheev.venue == 'Палац культури "Березіль" ім. Леся Курбаса'
    assert cheev.price_text == "від 350₴"
    assert cheev.ticket_url.endswith("/cheev-ternopil/")

    requested = [url for url, _ in calls]
    assert requested == [
        ticket_kiev.BASE_URL,
        "https://ticket.kiev.ua/ternopil/children/",
        "https://ticket.kiev.ua/ternopil/concert/",
        "https://ticket.kiev.ua/ternopil/stand-up/",
        "https://ticket.kiev.ua/ternopil/theater/",
    ]
    assert all(kwargs["timeout"] == 7.5 for _, kwargs in calls)
