from datetime import date
from types import SimpleNamespace

from app.collectors import ua_0352


LIVE_PAGE_HTML = '''
<html><body>
  <section>
    <h3>Інше</h3>
    <div class="event-card">
      <a href="/afisha/123/lunapark">Лунапарк</a>
      <div>15 - 16 серпня, 12:00</div>
      <div>Співоче поле</div>
    </div>
  </section>
</body></html>
'''


def test_0352_contract_points_to_ternopil_afisha():
    assert ua_0352.SOURCE_NAME == "0352.ua"
    assert ua_0352.BASE_URL == "https://www.0352.ua/afisha"


def test_0352_parses_observed_afisha_event_card(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(text=LIVE_PAGE_HTML, raise_for_status=lambda: None)

    monkeypatch.setattr(ua_0352.httpx, "get", fake_get)

    result = ua_0352.collect(timeout=7.5, days=0)

    assert len(result) == 1
    assert result[0].title == "Лунапарк"
    assert result[0].start_at.isoformat() == "2026-08-15T12:00:00"
    assert result[0].source_url.endswith("/afisha/123/lunapark")
    assert calls[0][0] == "https://www.0352.ua/afisha/2026-08-29"
    assert calls[0][1]["timeout"] == 7.5


def test_0352_parses_date_without_year_from_page_year():
    assert ua_0352._parse_start("15 - 16 серпня, 12:00", date(2026, 8, 29)).isoformat() == "2026-08-15T12:00:00"
