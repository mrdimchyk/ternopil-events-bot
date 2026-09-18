from datetime import datetime, timedelta, timezone

from app.services.event_identity import (
    extract_datetime_from_text,
    make_group_key,
    occurrence_variant_match,
    title_variant_match,
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


def test_title_variant_with_ticket_metadata_is_same_event():
    base = "Chico & Qatoshi x TIK | День Незалежності"
    scraped = (
        "Chico & Qatoshi x TIK | День Незалежності 22 серпня 2026 16:00 "
        "Тернопіль Агроленд від 600₴ Квитки"
    )
    assert title_variant_match(base, scraped)
    assert title_without_embedded_datetime(scraped) == base


def test_occurrence_variant_match_accepts_source_variants_within_tolerance():
    start = datetime(2026, 9, 20, 19, 0, tzinfo=timezone.utc)
    assert occurrence_variant_match(
        "Chico & Qatoshi x TIK | День Незалежності",
        start,
        "Na Пошті",
        "Chico & Qatoshi x TIK | День Незалежності 20 вересня 2026 19:10",
        start + timedelta(minutes=10),
        "Na Пошті, Тернопіль",
    )


def test_occurrence_variant_match_rejects_different_occurrence_time():
    start = datetime(2026, 9, 20, 19, 0)
    assert not occurrence_variant_match(
        "Вистава Великий вечір",
        start,
        "Драмтеатр",
        "Вистава Великий вечір",
        start + timedelta(minutes=16),
        "Драмтеатр",
    )
