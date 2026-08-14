from datetime import datetime

from app.collectors.line_catalog import _parse_date


def test_parse_date_with_explicit_year():
    assert _parse_date("01 серпня 2026, 19:00", 2026) == datetime(2026, 8, 1, 19, 0)


def test_parse_date_without_explicit_year():
    assert _parse_date("25 жовтня 18:00", 2026) == datetime(2026, 10, 25, 18, 0)
