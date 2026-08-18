from datetime import datetime

from app.db.models import Event, Venue
from app.services.event_queries import canonicalize_db_events


def make_event(
    event_id: int,
    group_key: str,
    title: str,
    source_id: int,
    ticket_url: str | None,
    start_at=None,
    venue_name: str | None = None,
):
    return Event(
        id=event_id,
        external_id=f"e{event_id}",
        group_key=group_key,
        title=title,
        start_at=start_at or datetime(2026, 10, 8, 18, 0),
        source_id=source_id,
        source_url=f"https://example.com/events/{event_id}",
        ticket_url=ticket_url,
        status="active",
        venue=Venue(name=venue_name) if venue_name else None,
    )


def test_canonical_query_collapses_duplicate_sources_and_keeps_offers():
    first = make_event(1, "same", "Я бачу, вас цікавить пітьма", 1, "https://karabas.com/1")
    second = make_event(2, "same", "Я бачу, вас цікавить пітьма", 2, "https://teatr.org.ua/1")
    third = make_event(3, "other", "Інша вистава", 1, "https://karabas.com/3")

    result = canonicalize_db_events([first, second, third])

    assert len(result) == 2
    duplicate = next(item for item in result if item.representative.group_key == "same")
    assert len(duplicate.sources) == 2
    assert {source.ticket_url for source in duplicate.sources} == {
        "https://karabas.com/1",
        "https://teatr.org.ua/1",
    }


def test_identical_title_same_time_is_deduplicated_even_with_different_group_keys():
    first = make_event(1, "a", "Одна вистава", 1, "https://example.com/1")
    second = make_event(2, "b", "Одна вистава", 2, "https://example.com/2")

    result = canonicalize_db_events([first, second])

    assert len(result) == 1
    assert len(result[0].sources) == 2


def test_repeated_event_at_two_times_is_shown_twice():
    first = make_event(
        1,
        "same",
        "ТІК. Найкраще",
        1,
        "https://example.com/16",
        datetime(2026, 8, 22, 16, 0),
    )
    second = make_event(
        2,
        "same",
        "ТІК. Найкраще",
        2,
        "https://example.com/19",
        datetime(2026, 8, 22, 19, 0),
    )

    result = canonicalize_db_events([first, second])

    assert len(result) == 2
    assert [item.representative.start_at.hour for item in result] == [16, 19]


def test_same_occurrence_with_date_in_title_is_deduplicated():
    first = make_event(
        1,
        "first-key",
        "Лос Янковерс. Колумбійці, які співають українські пісні",
        1,
        "https://example.com/1",
        datetime(2026, 9, 9, 18, 0),
    )
    second = make_event(
        2,
        "second-key",
        "Лос Янковерс. Колумбійці, які співають українські пісні 9 вересня 2026 18:00",
        2,
        "https://example.com/2",
        datetime(2026, 9, 9, 18, 0),
    )

    result = canonicalize_db_events([first, second])

    assert len(result) == 1
    assert len(result[0].sources) == 2


def test_same_occurrence_with_appended_source_metadata_is_deduplicated():
    first = make_event(
        1,
        "first-key",
        "Chico & Qatoshi x TIK | День Незалежності",
        1,
        "https://example.com/1",
        datetime(2026, 8, 22, 16, 0),
    )
    second = make_event(
        2,
        "second-key",
        "Chico & Qatoshi x TIK | День Незалежності 22 серпня 2026 16:00 Тернопіль Агроленд від 600₴ Квитки",
        2,
        "https://example.com/2",
        datetime(2026, 8, 22, 16, 0),
    )

    result = canonicalize_db_events([first, second])

    assert len(result) == 1
    assert len(result[0].sources) == 2


def test_same_occurrence_with_venue_name_variant_is_deduplicated():
    first = make_event(
        1,
        "first-key",
        "Jamala",
        1,
        "https://example.com/1",
        datetime(2026, 9, 13, 19, 0),
        'Тернопільський міський палац культури "Березіль" ім. Леся Курбаса',
    )
    second = make_event(
        2,
        "second-key",
        "Jamala",
        2,
        "https://example.com/2",
        datetime(2026, 9, 13, 19, 0),
        'Палац культури "Березіль" ім. Леся Курбаса',
    )

    result = canonicalize_db_events([first, second])

    assert len(result) == 1
    assert len(result[0].sources) == 2


def test_canonicalization_is_stable_for_three_transitive_source_variants():
    start = datetime(2026, 9, 13, 19, 0)
    first = make_event(1, "source-a", "Jamala", 1, "https://example.com/a", start, "Палац культури Березіль")
    second = make_event(2, "source-b", "Jamala — квитки", 2, "https://example.com/b", start, "Палац культури Березіль")
    third = make_event(3, "source-c", "Jamala", 3, "https://example.com/c", start, "Тернопільський міський палац культури Березіль")

    result = canonicalize_db_events([first, second, third])

    assert len(result) == 1
    assert {source.group_key for source in result[0].sources} == {"source-a", "source-b", "source-c"}
