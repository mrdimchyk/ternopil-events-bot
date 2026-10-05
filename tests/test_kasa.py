from datetime import datetime

from app.collectors.kasa import _parse_venue_page, _venue_urls


CITY_HTML = """
<html><body>
<h2>Події у Тернопіль</h2>
<h2>Майданчики Тернопіль</h2>
<a href="/ternopilska_oblasna_filarmoniya-t1143831314">Тернопільська обласна філармонія</a>
<a href="/palac_kulturi_berezil_im_lesya_kurbasa-t139898709">Палац культури «Березіль»</a>
<h2>Квитки у Тернопіль</h2>
</body></html>
"""

VENUE_HTML = """
<html><body>
<h1>Купити квитки в «Тернопільська обласна філармонія» (Тернопіль) онлайн 2026</h1>
<div>
  <a href="/event/vech-na-vech">«Концерт ВІЧ-НА-ВІЧ»</a>
  <div>Тернопільська обласна філармонія</div>
  <div>Четвер 2026/08/27</div>
  <div>Час початку 18:30</div>
  <div>Ціна від 200 грн</div>
  <a href="/event/vech-na-vech">Придбати квиток</a>
</div>
<div>
  <a href="/event/panna-francishka">«Мюзикл «Панна Францішка»»</a>
  <div>Тернопільська обласна філармонія</div>
  <div>Неділя 2026/08/30</div>
  <div>Час початку 17:00</div>
  <div>Ціна від 200 грн</div>
  <a href="/event/panna-francishka">Придбати квиток</a>
</div>
<div>
  <a href="/event/old_1">«Відкриття концертного сезону»</a>
  <div>Тернопільська обласна філармонія</div>
  <div>Неділя 2026/08/23</div>
  <div>Час початку 17:00</div>
  <div>Подія вже відбулася</div>
</div>
</body></html>
"""


def test_kasa_city_page_exposes_venue_catalog_links():
    assert _venue_urls(CITY_HTML) == [
        "https://kasa.com.ua/ternopilska_oblasna_filarmoniya-t1143831314",
        "https://kasa.com.ua/palac_kulturi_berezil_im_lesya_kurbasa-t139898709",
    ]


def test_kasa_parses_observed_current_venue_contract_and_filters_past_events():
    events = _parse_venue_page(
        VENUE_HTML,
        "https://kasa.com.ua/ternopilska_oblasna_filarmoniya-t1143831314",
        datetime(2026, 8, 29, 9, 0),
    )

    assert len(events) == 1
    event = events[0]
    assert event.title == "Мюзикл «Панна Францішка»"
    assert event.start_at == datetime(2026, 8, 30, 17, 0)
    assert event.venue == "Тернопільська обласна філармонія"
    assert event.price_text == "Ціна від 200 грн"
    assert event.ticket_url == "https://kasa.com.ua/event/panna-francishka"
    assert event.external_id


def test_kasa_retries_transient_timeout_then_returns_response(monkeypatch):
    import httpx
    from app.collectors.kasa import _get_with_retry
    attempts = []
    monkeypatch.setattr('app.collectors.kasa.time.sleep', lambda seconds: None)

    def get(url):
        attempts.append(url)
        if len(attempts) < 3:
            raise httpx.ReadTimeout('The read operation timed out')
        return httpx.Response(200, text=CITY_HTML, request=httpx.Request('GET', url))

    assert _get_with_retry(get, 'https://kasa.com.ua/ternopol/').text == CITY_HTML
    assert len(attempts) == 3


def test_kasa_exhausted_timeouts_still_fail_and_http_errors_are_not_retried(monkeypatch):
    import httpx
    import pytest
    from app.collectors.kasa import _get_with_retry
    attempts = []
    monkeypatch.setattr('app.collectors.kasa.time.sleep', lambda seconds: None)

    def get(url):
        attempts.append(url)
        raise httpx.ReadTimeout('timeout')

    with pytest.raises(httpx.ReadTimeout):
        _get_with_retry(get, 'https://kasa.com.ua/ternopol/')
    assert len(attempts) == 3
    attempts.clear()

    def forbidden(url):
        attempts.append(url)
        return httpx.Response(403, request=httpx.Request('GET', url))

    with pytest.raises(httpx.HTTPStatusError):
        _get_with_retry(forbidden, 'https://kasa.com.ua/ternopol/')
    assert len(attempts) == 1
