from datetime import datetime

from app.db.models import Event
from app.services.event_queries import canonicalize_db_events


def make_event(event_id: int, group_key: str, title: str, source_id: int, ticket_url: str | None):
    return Event(
        id=event_id,
        external_id=f"e{event_id}",
        group_key=group_key,
        title=title,
        start_at=datetime(2026, 10, 8, 18, 0),
        source_id=source_id,
        source_url=f"https://example.com/events/{event_id}",
        ticket_url=ticket_url,
        status="active",
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


def test_canonical_query_does_not_merge_different_group_keys():
    first = make_event(1, "a", "Одна вистава", 1, "https://example.com/1")
    second = make_event(2, "b", "Одна вистава", 2, "https://example.com/2")

    result = canonicalize_db_events([first, second])

    assert len(result) == 2
    assert all(len(item.sources) == 1 for item in result)
