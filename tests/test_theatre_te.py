from datetime import datetime

from app.collectors.theatre_te import _parse_cards


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
