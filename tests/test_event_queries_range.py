from datetime import datetime

from app.db.models import Event
from app.services.event_queries import canonicalize_db_events


def make_event(event_id: int, group_key: str, category: str | None, day: int) -> Event:
    return Event(
        id=event_id,
        external_id=f"e{event_id}",
        group_key=group_key,
        title=f"Подія {event_id}",
        category=category,
        start_at=datetime(2026, 8, day, 19, 0),
        source_id=1,
        source_url=f"https://example.com/{event_id}",
        status="active",
    )


def test_range_canonicalization_keeps_one_event_per_group():
    events = [
        make_event(1, "same", "theatre", 22),
        make_event(2, "same", "theatre", 22),
        make_event(3, "other", "concert", 23),
    ]
    result = canonicalize_db_events(events)
    assert len(result) == 2
    assert len(result[0].sources) == 2
