from types import SimpleNamespace

from app.collectors import murava, ticket_dp


TICKET_HTML = """
<html><body>
<a href="/event/irena-karpa">350 Ірена Карпа. Літературний стендап 29 вересня 2026 (19:00) Тернопільська обласна філармонія</a>
<a href="/event/wellboy">800 WellBoy 18 вересня 2026 (18:00) Сонcert Hall PODOLYANY</a>
<a href="/event/category">Концерт</a>
</body></html>
"""

MURAVA_HTML = """
<html><body>
<section>
  <div class="event">
    <span>4 вересня 2026 ПТ</span>
    <img alt="КУРГАН &amp; AGREGAT ТА KARNA">
    <a href="https://concert.ua/uk/event/murava">Купити квиток</a>
  </div>
</section>
</body></html>
"""


def _response(html: str):
    return SimpleNamespace(text=html, raise_for_status=lambda: None)


def test_ticket_dp_parser_matches_live_event_card_contract(monkeypatch):
    monkeypatch.setattr(ticket_dp.httpx, "get", lambda *args, **kwargs: _response(TICKET_HTML))

    events = ticket_dp.collect()

    assert len(events) == 2
    assert events[0].title == "Ірена Карпа. Літературний стендап"
    assert events[0].start_at.strftime("%Y-%m-%d %H:%M") == "2026-09-29 19:00"
    assert events[0].venue == "Тернопільська обласна філармонія"
    assert events[0].price_text == "350 грн"
    assert events[1].title == "WellBoy"


def test_murava_parser_matches_official_event_block_contract(monkeypatch):
    monkeypatch.setattr(murava.httpx, "get", lambda *args, **kwargs: _response(MURAVA_HTML))

    events = murava.collect()

    assert len(events) == 1
    assert events[0].title == "КУРГАН & AGREGAT ТА KARNA"
    assert events[0].start_at.strftime("%Y-%m-%d %H:%M") == "2026-09-04 00:00"
    assert events[0].venue == "MURAVA PARK RELAX"
    assert events[0].ticket_url == "https://concert.ua/uk/event/murava"
