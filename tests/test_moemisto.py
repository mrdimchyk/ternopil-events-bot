from datetime import datetime
from types import SimpleNamespace

from app.collectors import moemisto


LIVE_CARD_HTML = '''
<html><body>
  <section class="event-card">
    <a href="/te/antytila-u-ternopoli-290001.html">АНТИТІЛА у Тернополі</a>
    <div>Палац культури "Березіль" 21 листопада 19:00 Тернопіль Концерт від 490 грн</div>
  </section>
  <section class="event-card">
    <a href="/te/park-legend-u-ternopoli-290002.html">Магічний "Парк Легенд" у Тернополі</a>
    <div>Парк ім. Т.Г.Шевченка 27 - 31 серпня Тернопіль Дітям від 100 грн</div>
  </section>
</body></html>
'''


def test_moemisto_contract_points_to_ternopil_catalog():
    assert moemisto.SOURCE_NAME == "moemisto.ua"
    assert moemisto.BASE_URL == "https://moemisto.ua/te"


def test_moemisto_parses_observed_event_card_contract_and_filters_past(monkeypatch):
    calls = {}

    def fake_get(url, **kwargs):
        calls.update(url=url, **kwargs)
        return SimpleNamespace(text=LIVE_CARD_HTML, raise_for_status=lambda: None)

    monkeypatch.setattr(moemisto.httpx, "get", fake_get)

    result = moemisto.collect(timeout=7.5, now=datetime(2026, 8, 29, 10, 0))

    assert len(result) == 1
    assert result[0].title == "АНТИТІЛА у Тернополі"
    assert result[0].start_at.isoformat() == "2026-11-21T19:00:00"
    assert result[0].venue == 'Палац культури "Березіль"'
    assert result[0].price_text == "від 490 грн"
    assert calls["url"] == moemisto.BASE_URL
    assert calls["timeout"] == 7.5


def test_moemisto_preserves_future_multi_day_event_start():
    assert moemisto._parse_start("27 - 31 серпня", datetime(2026, 8, 20)).isoformat() == "2026-08-27T00:00:00"
