from types import SimpleNamespace

from app.collectors import list_in_ua


LIVE_CARD_HTML = '''
<html><body>
  <div class="event-card">
    <a href="/Тернопіль/afisha/179999-Mindgame">
      Mindgame. Гра про Україну
    </a>
    <div>25.08.2026 19:00 300 грн</div>
    <a href="/Тернопіль/company/999-restaurant-oskar">Ресторан "Оскар"</a>
  </div>
</body></html>
'''


def test_list_in_ua_contract_points_to_upcoming_ternopil_catalog():
    assert list_in_ua.SOURCE_NAME == "List.in.ua"
    assert list_in_ua.BASE_URL.endswith("%D0%A2%D0%B5%D1%80%D0%BD%D0%BE%D0%BF%D1%96%D0%BB%D1%8C/afisha/soon")


def test_list_in_ua_parses_observed_event_card_structure(monkeypatch):
    calls = {}

    def fake_get(url, **kwargs):
        calls.update(url=url, **kwargs)
        return SimpleNamespace(text=LIVE_CARD_HTML, raise_for_status=lambda: None)

    monkeypatch.setattr(list_in_ua.httpx, "get", fake_get)

    result = list_in_ua.collect(timeout=7.5)

    assert len(result) == 1
    event = result[0]
    assert event.title == "Mindgame. Гра про Україну"
    assert event.start_at.isoformat() == "2026-08-25T19:00:00"
    assert event.venue == 'Ресторан "Оскар"'
    assert event.price_text == "300 грн"
    assert event.ticket_url.endswith("/Тернопіль/afisha/179999-Mindgame")
    assert calls["url"] == list_in_ua.BASE_URL
    assert calls["timeout"] == 7.5
