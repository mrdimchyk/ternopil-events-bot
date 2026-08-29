from datetime import datetime

from app.collectors.pulselive import _parse


HTML = """
<html><body>
<section>
  <article>
    <a href="/events/wellboy-ternopil">
      <h3>WELLBOY. Пасажир. Великий сольний концерт</h3>
      <div>18 вересня 2026 · 18:00</div>
      <div>Тернопіль · Concert Hall Podolyany</div>
      <div>Квитки від 800 ₴</div>
    </a>
  </article>
  <article>
    <a href="/events/wellboy-lutsk">
      <h3>WELLBOY. Пасажир. Великий сольний концерт</h3>
      <div>20 вересня 2026 · 19:00</div>
      <div>Луцьк · Кіноконцертна зала РЦ «Промінь»</div>
      <div>Квитки від 350 ₴</div>
    </a>
  </article>
</section>
</body></html>
"""


def test_pulselive_parses_observed_ternopil_card_contract():
    events = _parse(
        HTML,
        "https://pulselive.com.ua/kontserty",
        datetime(2026, 8, 29, 12, 0),
    )
    assert len(events) == 1
    event = events[0]
    assert event.title == "WELLBOY. Пасажир. Великий сольний концерт"
    assert event.start_at == datetime(2026, 9, 18, 18, 0)
    assert event.venue == "Concert Hall Podolyany"
    assert event.price_text == "Квитки від 800 ₴"
    assert event.ticket_url == "https://pulselive.com.ua/events/wellboy-ternopil"
    assert event.external_id
