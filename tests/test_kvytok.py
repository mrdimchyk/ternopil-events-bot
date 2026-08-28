from types import SimpleNamespace

from app.collectors import kvytok


LIVE_CARD_HTML = '''
<html><body>
  <section class="event-card">
    <h5>Брешемо чисту правду</h5>
    <div>07.09 18:00 Тернопіль Тернопільський академічний обласний український драматичний театр Т. Г. Шевченка</div>
    <a href="/breshuemo-chistu-pravdu-ternopil/">Квитки</a>
  </section>
  <section class="event-card">
    <h5>WellBoy</h5>
    <div>18.09 18:00 Тернопіль Сонcert Hall PODOLYANY</div>
    <a href="/wellboy-ternopil/">Квитки</a>
  </section>
</body></html>
'''


def test_kvytok_contract_points_to_ternopil_catalog():
    assert kvytok.SOURCE_NAME == "Kvytok"
    assert kvytok.BASE_URL == "https://kvytok.co/ternopil/"


def test_kvytok_parses_observed_event_card_contract(monkeypatch):
    calls = {}

    def fake_get(url, **kwargs):
        calls.update(url=url, **kwargs)
        return SimpleNamespace(text=LIVE_CARD_HTML, raise_for_status=lambda: None)

    monkeypatch.setattr(kvytok.httpx, "get", fake_get)

    result = kvytok.collect(timeout=7.5)

    assert len(result) == 2
    assert result[0].title == "Брешемо чисту правду"
    assert result[0].start_at.isoformat() == "2026-09-07T18:00:00"
    assert result[0].venue == "Тернопільський академічний обласний український драматичний театр Т. Г. Шевченка"
    assert result[0].ticket_url.endswith("/breshuemo-chistu-pravdu-ternopil/")
    assert result[1].title == "WellBoy"
    assert result[1].start_at.isoformat() == "2026-09-18T18:00:00"
    assert result[1].venue == "Сонcert Hall PODOLYANY"
    assert calls["url"] == kvytok.BASE_URL
    assert calls["timeout"] == 7.5
