from datetime import datetime

from app.collectors.base import RawEvent
from app.services.canonical_events import build_canonical_events


def event(external_id: str, title: str, source_url: str) -> RawEvent:
    return RawEvent(
        external_id=external_id,
        title=title,
        category="theatre",
        start_at=datetime(2026, 10, 8, 18, 0),
        venue="Тернопільський драмтеатр",
        address="Тернопіль",
        price_text="500 грн",
        ticket_url="https://example.com/tickets/" + external_id,
        source_url=source_url,
    )


def test_matching_sources_are_one_canonical_event():
    result = build_canonical_events(
        {
            "KARABAS": [event("k1", "Я бачу, вас цікавить пітьма", "https://karabas.com/1")],
            "Teatr.org.ua": [event("t1", "Я бачу, вас цікавить пітьма", "https://teatr.org.ua/1")],
        }
    )

    assert len(result) == 1
    assert len(result[0].sources) == 2
    assert {source.source for source in result[0].sources} == {"KARABAS", "Teatr.org.ua"}


def test_different_events_remain_separate():
    first = event("k1", "Я бачу, вас цікавить пітьма", "https://karabas.com/1")
    second = event("k2", "Хор Гомін", "https://karabas.com/2")
    result = build_canonical_events({"KARABAS": [first, second]})

    assert len(result) == 2
