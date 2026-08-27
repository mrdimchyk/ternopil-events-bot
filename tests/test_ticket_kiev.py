from types import SimpleNamespace

from app.collectors import ticket_kiev


LIVE_CARD_HTML = '''
<html><body>
  <div class="event-card">
    <a href="/cheev-ternopil/">
      <h3>CHEEV</h3>
    </a>
    <div>Концерт 25 жовтня 2026 19:00 Тернопіль Палац культури "Березіль" ім. Леся Курбаса від 350₴</div>
  </div>
</body></html>
'''


def test_ticket_kiev_contract_points_to_ternopil_catalog():
    assert ticket_kiev.SOURCE_NAME == "Ticket.kiev.ua"
    assert ticket_kiev.BASE_URL == "https://ticket.kiev.ua/ternopil/"


def test_ticket_kiev_parses_observed_event_card_structure(monkeypatch):
    calls = {}

    def fake_get(url, **kwargs):
        calls.update(url=url, **kwargs)
        return SimpleNamespace(text=LIVE_CARD_HTML, raise_for_status=lambda: None)

    monkeypatch.setattr(ticket_kiev.httpx, "get", fake_get)

    result = ticket_kiev.collect(timeout=7.5)

    assert len(result) == 1
    event = result[0]
    assert event.title == "CHEEV"
    assert event.start_at.isoformat() == "2026-10-25T19:00:00"
    assert event.venue == 'Палац культури "Березіль" ім. Леся Курбаса'
    assert event.price_text == "350₴"
    assert event.ticket_url.endswith("/cheev-ternopil/")
    assert calls["url"] == ticket_kiev.BASE_URL
    assert calls["timeout"] == 7.5
