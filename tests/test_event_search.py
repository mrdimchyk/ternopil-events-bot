from datetime import datetime

from app.db.models import Event
from app.services.event_queries import canonicalize_db_events


def make_event(event_id: int, group_key: str, title: str, source_id: int) -> Event:
    return Event(
        id=event_id,
        external_id=f"e{event_id}",
        group_key=group_key,
        title=title,
        start_at=datetime(2026, 10, 8, 18, 0),
        source_id=source_id,
        source_url=f"https://example.com/{event_id}",
        status="active",
    )


def test_search_results_are_canonicalized():
    events = [
        make_event(1, "same", "Я бачу, вас цікавить пітьма", 1),
        make_event(2, "same", "Я бачу, вас цікавить пітьма", 2),
        make_event(3, "other", "Інша вистава", 1),
    ]
    result = canonicalize_db_events([event for event in events if "пітьма" in event.title.lower()])
    assert len(result) == 1
    assert len(result[0].sources) == 2
