from datetime import datetime

from app.collectors.karabas import _extract_events, _parse_date_time


def test_karabas_parses_month_heading_with_weekday_and_apostrophe():
    value = "19 Ср серпня ’ 2026 19:00"
    parsed = _parse_date_time(value)
    assert parsed == datetime(2026, 8, 19, 19, 0)


def test_karabas_extracts_event_from_month_page_text():
    text = """19 Ср серпня ’ 2026
Концерти
Тестовий концерт
Тернопіль
Concert Hall
19:00
300 - 650 грн
Купити
20 Чт серпня ’ 2026
"""
    events = _extract_events(text, "https://ternopil.karabas.com/august/", datetime(2026, 8, 15, 0, 0))
    assert len(events) == 1
    assert events[0].title == "Тестовий концерт"
    assert events[0].start_at == datetime(2026, 8, 19, 19, 0)
    assert events[0].venue == "Concert Hall"
    assert events[0].price_text == "300 - 650 грн"


def test_karabas_skips_cancelled_events():
    text = """19 Ср серпня ’ 2026
Скасовано
Скасований концерт
Тернопіль
Concert Hall
19:00
300 грн
Купити
20 Чт серпня ’ 2026
"""
    events = _extract_events(text, "https://ternopil.karabas.com/august/", datetime(2026, 8, 15, 0, 0))
    assert events == []
