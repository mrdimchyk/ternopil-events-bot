from datetime import datetime

import app.collectors.theatre_te as theatre_te
from app.collectors.theatre_te import _pagination_urls, _parse_cards


HTML = """
<html><body>
<main>
  <h1>Репертуар</h1>
  <article class="event-card">
    <h3>До 170-ї річниці від Дня народження Івана Франка. Прем`єра. «Украдене щастя»</h3>
    <div>нд, 27 вересня 2026 р. 18:00</div>
    <div>драма</div>
    <div>₴ 200-350</div>
    <a>Купити</a>
  </article>
  <article class="event-card">
    <h3>«Аладдін»</h3>
    <div>нд, 4 жовтня 2026 р. 13:00</div>
    <div>музична казка</div>
    <div>₴ 150-200</div>
    <a>Купити</a>
  </article>
</main>
</body></html>
"""


def test_theatre_parses_observed_repertory_cards():
    events = _parse_cards(HTML, datetime(2026, 9, 15, 11, 0))
    assert len(events) == 2
    assert events[0].title == "До 170-ї річниці від Дня народження Івана Франка. Прем`єра. «Украдене щастя»"
    assert events[0].start_at == datetime(2026, 9, 27, 18, 0)
    assert events[0].price_text == "200-350"
    assert events[0].venue == "Тернопільський академічний театр ім. Т. Г. Шевченка"
    assert events[1].title == "«Аладдін»"
    assert events[1].start_at == datetime(2026, 10, 4, 13, 0)


def test_theatre_skips_past_events():
    events = _parse_cards(HTML, datetime(2026, 10, 5, 12, 0))
    assert events == []


def test_theatre_discovers_all_repertory_pagination_pages():
    html = """
    <nav>
      <a href="/repertory">1</a>
      <a href="/repertory/page/2">2</a>
      <a href="https://www.theatre.te.ua/repertory/page/3/">3</a>
      <a href="/news/page/2">news</a>
    </nav>
    """
    assert _pagination_urls(html) == [
        "https://www.theatre.te.ua/repertory",
        "https://www.theatre.te.ua/repertory/page/2",
        "https://www.theatre.te.ua/repertory/page/3",
    ]


def test_theatre_collect_fetches_and_combines_paginated_repertory(monkeypatch):
    def page(title: str, day: int, pagination: str = "") -> str:
        return f"""
        <html><body>
          {pagination}
          <article>
            <h3>{title}</h3>
            <div>сб, {day} жовтня 2099 р. 18:00</div>
            <div>₴ 200</div>
          </article>
        </body></html>
        """

    pages = {
        theatre_te.BASE_URL: page(
            "Сторінка 1",
            1,
            '<a href="/repertory/page/2">2</a><a href="/repertory/page/3">3</a>',
        ),
        f"{theatre_te.BASE_URL}/page/2": page("Сторінка 2", 2),
        f"{theatre_te.BASE_URL}/page/3": page("Сторінка 3", 3),
    }
    requested = []

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return self

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            requested.append(url)
            return FakeResponse(pages[url])

    monkeypatch.setattr(theatre_te.httpx, "Client", FakeClient)

    events = theatre_te.collect()

    assert requested == [
        theatre_te.BASE_URL,
        f"{theatre_te.BASE_URL}/page/2",
        f"{theatre_te.BASE_URL}/page/3",
    ]
    assert [event.title for event in events] == ["Сторінка 1", "Сторінка 2", "Сторінка 3"]
