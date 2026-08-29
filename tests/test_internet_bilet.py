from datetime import datetime

from app.collectors.internet_bilet import _collect_from_html


FIXTURE = """
<div>
  <a href="/uk/shugar-brykulec">
    <img alt="ШУГАР ✘ BRYKULETS ✘ СТЕПАН ТА КВІТОСЛАВА ГІГА">
  </a>
  <div>
    Тернопіль Етнопарк «Агроленд»
    600 грн Залишилось квитків: 400
    <a href="/uk/shugar-brykulec">ШУГАР ✘ BRYKULETS ✘ СТЕПАН ТА КВІТОСЛАВА ГІГА</a>
    6 вересня, 16:00
    <a href="/uk/shugar-brykulec">Купити квитки</a>
  </div>
</div>
<div>
  <a href="/uk/mamarika">MamaRika</a>
  <div>
    Тернопіль ПК "Березіль"
    Відміна заходу
    8 вересня, 18:00
  </div>
</div>
"""


def test_parses_observed_ternopil_event_card_structure():
    events = _collect_from_html(FIXTURE, now=datetime(2026, 8, 29, 7, 0))

    assert len(events) == 1
    event = events[0]
    assert event.title == "ШУГАР ✘ BRYKULETS ✘ СТЕПАН ТА КВІТОСЛАВА ГІГА"
    assert event.start_at == datetime(2026, 9, 6, 16, 0)
    assert event.venue == 'Етнопарк «Агроленд»'
    assert event.price_text == "600 грн"
    assert event.ticket_url == "https://ternopil.internet-bilet.ua/uk/shugar-brykulec"


def test_deduplicates_same_event_link():
    html = FIXTURE.replace(
        '</div>\n</div>\n<div>',
        '</div>\n</div>\n<div>',
    )
    events = _collect_from_html(html, now=datetime(2026, 8, 29, 7, 0))
    assert len({event.external_id for event in events}) == len(events)
