from datetime import datetime

from app.services.event_identity import (
    extract_datetime_from_text,
    make_group_key,
    title_without_embedded_datetime,
)


def test_same_event_from_two_sources_gets_same_group_key():
    start = datetime(2026, 9, 20, 19, 0)
    assert make_group_key("Concert Test", start, "Na Пошті") == make_group_key(
        "concert test", start, "Na Пошті"
    )


def test_extract_datetime_from_ukrainian_title():
    value = extract_datetime_from_text("ТІК 22 серпня 2026 16:00")
    assert value == datetime(2026, 8, 22, 16, 0)


def test_extract_date_without_time_uses_midnight():
    value = extract_datetime_from_text("ТІК 22 серпня 2026", default_year=2025)
    assert value == datetime(2026, 8, 22, 0, 0)


def test_title_without_embedded_datetime():
    title = "ТІК. Найкраще 22 серпня 2026 16:00"
    assert title_without_embedded_datetime(title) == "ТІК. Найкраще"
