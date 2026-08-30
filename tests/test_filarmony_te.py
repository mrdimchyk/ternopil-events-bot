from datetime import datetime

from app.collectors.filarmony_te import _parse_cards


HTML = """
<html><body>
<nav>АФІША НОВИНИ АДМІНІСТРАЦІЯ</nav>
<section class="event-card">
  <h2>«АNІМЕ MUSIC»</h2>
  <p>мелодії з улюблених аніме наживо!</p>
  <p>27 вересня о 17:00 звучатимуть мелодії з улюблених аніме.</p>
  <p>Квитки у касі філармонії та на Karabas.com</p>
  <div>27вересня(неділя)17:00Ціна квитків: 200-400 грн.</div>
</section>
<section class="event-card">
  <h2>«МУЗИКА ВЕЛИКОГО ЕКРАНУ»</h2>
  <p>Академічний симфонічний оркестр запрошує на вечір легендарної кіномузики.</p>
  <div>9вересня(середа)18:30Ціна квитків: 200-350 грн.</div>
</section>
</body></html>
"""


def test_filarmony_parses_observed_event_card_structure():
    events = _parse_cards(HTML, datetime(2026, 8, 1, 12, 0))
    assert len(events) == 2
    assert events[0].title == "«АNІМЕ MUSIC»"
    assert events[0].start_at == datetime(2026, 9, 27, 17, 0)
    assert events[0].price_text == "200-400 грн."
    assert events[0].venue == "Тернопільська обласна філармонія"
    assert events[1].title == "«МУЗИКА ВЕЛИКОГО ЕКРАНУ»"
    assert events[1].start_at == datetime(2026, 9, 9, 18, 30)


def test_filarmony_skips_past_events():
    events = _parse_cards(HTML, datetime(2026, 10, 1, 12, 0))
    assert events == []
