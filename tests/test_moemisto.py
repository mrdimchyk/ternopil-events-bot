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


def test_moemisto_discovers_category_catalogs_only():
    html = """
    <nav>
      <a href="/te/kontserti">Концерти</a>
      <a href="/te/vidpochinok">Відпочинок</a>
      <a href="/te/dityam">Дітям</a>
      <a href="/te/some-event-123.html">Концерти</a>
      <a href="https://example.com/te/theatre">Театр</a>
    </nav>
    """

    assert moemisto._category_urls(html) == [
        "https://moemisto.ua/te/dityam",
        "https://moemisto.ua/te/kontserti",
        "https://moemisto.ua/te/vidpochinok",
    ]


def test_moemisto_collects_category_only_events_and_deduplicates(monkeypatch):
    base_html = """
    <html><body>
      <nav>
        <a href="/te/kontserti">Концерти</a>
        <a href="/te/dityam">Дітям</a>
      </nav>
      <section class="event-card">
        <a href="/te/cheev-300001.html">CHEEV</a>
        <div>Палац культури "Березіль" 25 жовтня 19:00 Тернопіль Концерт від 350 грн</div>
      </section>
    </body></html>
    """
    concert_html = """
    <html><body>
      <section class="event-card">
        <a href="/te/cheev-300001.html">CHEEV</a>
        <div>Палац культури "Березіль" 25 жовтня 19:00 Тернопіль Концерт від 350 грн</div>
      </section>
      <section class="event-card">
        <a href="/te/tnmk-300002.html">ТНМК з концертом у Тернополі</a>
        <div>Палац культури "Березіль" 12 листопада 19:00 Тернопіль Концерт 500 грн</div>
      </section>
    </body></html>
    """
    children_html = """
    <html><body>
      <section class="event-card">
        <a href="/te/kids-300003.html">Дитяча вистава</a>
        <div>Театр ім. Шевченка 2 жовтня 12:00 Тернопіль Дітям 200 грн</div>
      </section>
    </body></html>
    """
    pages = {
        moemisto.BASE_URL: base_html,
        "https://moemisto.ua/te/kontserti": concert_html,
        "https://moemisto.ua/te/dityam": children_html,
    }
    requested = []

    def fake_get(url, **kwargs):
        requested.append((url, kwargs))
        return SimpleNamespace(text=pages[url], raise_for_status=lambda: None)

    monkeypatch.setattr(moemisto.httpx, "get", fake_get)

    result = moemisto.collect(
        timeout=7.5,
        now=datetime(2026, 9, 20, 12, 0),
    )

    assert [event.title for event in result] == [
        "CHEEV",
        "Дитяча вистава",
        "ТНМК з концертом у Тернополі",
    ]
    assert [url for url, _ in requested] == [
        moemisto.BASE_URL,
        "https://moemisto.ua/te/dityam",
        "https://moemisto.ua/te/kontserti",
    ]
    assert all(kwargs["timeout"] == 7.5 for _, kwargs in requested)
