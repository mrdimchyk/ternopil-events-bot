from datetime import datetime

from bs4 import BeautifulSoup

from app.collectors.moemisto import _parse_start, _title, _venue


def test_moemisto_live_card_structure_parses_observed_fields():
    html = """
    <div class="event-card">
      <a href="https://moemisto.ua/te/park-legend-123.html">Магічний \"Парк Легенд\" у Тернополі</a>
      <div>Парк ім. Т.Г.Шевченка</div>
      <div>28 - 31 серпня</div>
      <div>від 100 грн</div>
      <div>Дітям</div>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    anchor = soup.select_one("a[href]")
    assert anchor is not None
    block = anchor.parent
    text = " ".join(block.stripped_strings)
    now = datetime(2026, 8, 28, 12, 0)

    start_at = _parse_start(text, now)
    title = _title(anchor, block)

    assert start_at == datetime(2026, 8, 28, 0, 0)
    assert title == 'Магічний "Парк Легенд" у Тернополі'
    assert _venue(text, title) == "Парк ім. Т.Г.Шевченка"
    assert "від 100 грн" in text


def test_moemisto_observed_event_date_with_time_is_supported():
    now = datetime(2026, 8, 28, 12, 0)
    assert _parse_start("21 листопада 19:00", now) == datetime(2026, 11, 21, 19, 0)
