from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from app.collectors.line_catalog import _clean, _parse_lines


FIXTURE = Path(__file__).parent / "fixtures" / "ticketsbox_catalog.html"


def _fixture_lines():
    soup = BeautifulSoup(FIXTURE.read_text(encoding="utf-8"), "lxml")
    return [_clean(value) for value in soup.stripped_strings if _clean(value)]


def test_ticketsbox_fixture_keeps_future_event_and_drops_ended_event():
    events = _parse_lines(
        _fixture_lines(),
        "https://ternopil.ticketsbox.com/",
        2026,
        datetime(2026, 8, 17, 15, 0),
    )

    assert len(events) == 1
    assert events[0].title == "Тестова подія TicketsBox"
    assert events[0].start_at == datetime(2026, 8, 20, 19, 0)
    assert events[0].price_text == "300 грн"
    assert events[0].venue == "Тестовий майданчик"


def test_ticketsbox_fixture_preserves_city_and_category():
    events = _parse_lines(
        _fixture_lines(),
        "https://ternopil.ticketsbox.com/",
        2026,
        datetime(2026, 8, 17, 15, 0),
    )

    assert events[0].category == "concert"
    assert events[0].source_url == "https://ternopil.ticketsbox.com/"
