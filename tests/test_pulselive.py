from datetime import datetime

from app.collectors.pulselive import _parse


HTML = """
<html><body>
<section>
  <article>
    <a href="/events/wellboy-ternopil">
      <span>18вересня</span>
      <h3>WELLBOY. Пасажир. Великий сольний концерт</h3>
    </a>
    <div>Тернопіль · Concert Hall Podolyany</div>
    <div>18 вересня 2026 · 18:00</div>
    <div>Квитки від800 ₴</div>
  </article>
  <article>
    <a href="/events/wellboy-lutsk">
      <span>20вересня</span>
      <h3>WELLBOY. Пасажир. Великий сольний концерт</h3>
    </a>
    <div>Луцьк · Кіноконцертна зала РЦ «Промінь»</div>
    <div>20 вересня 2026 · 19:00</div>
    <div>Квитки від350 ₴</div>
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
