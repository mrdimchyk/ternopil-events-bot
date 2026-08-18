import json
from datetime import datetime, timezone
from pathlib import Path

from app.collectors.base import RawEvent
from app.services.canonical_events import build_canonical_events


def event(external_id: str, title: str, source_url: str, start_at: datetime | None = None) -> RawEvent:
    return RawEvent(
        external_id=external_id,
        title=title,
        category="theatre",
        start_at=start_at or datetime(2026, 10, 8, 18, 0),
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


def test_canonical_event_preserves_each_source_ticket_and_price():
    first = event("k1", "Я бачу, вас цікавить пітьма", "https://karabas.com/1")
    second = event("t1", "Я бачу, вас цікавить пітьма", "https://teatr.org.ua/1")
    second.price_text = "600 грн"
    canonical = build_canonical_events({"KARABAS": [first], "Teatr.org.ua": [second]})[0]
    sources = {source.source: source for source in canonical.sources}
    assert sources["KARABAS"].source_url == "https://karabas.com/1"
    assert sources["KARABAS"].ticket_url == "https://example.com/tickets/k1"
    assert sources["KARABAS"].price_text == "500 грн"
    assert sources["Teatr.org.ua"].source_url == "https://teatr.org.ua/1"
    assert sources["Teatr.org.ua"].ticket_url == "https://example.com/tickets/t1"
    assert sources["Teatr.org.ua"].price_text == "600 грн"


def test_canonical_key_is_stable_when_source_order_changes():
    karabas = event("k1", "Я бачу, вас цікавить пітьма", "https://karabas.com/1")
    teatr = event("t1", "Я бачу, вас цікавить пітьма", "https://teatr.org.ua/1")
    first = build_canonical_events({"KARABAS": [karabas], "Teatr.org.ua": [teatr]})[0]
    second = build_canonical_events({"Teatr.org.ua": [teatr], "KARABAS": [karabas]})[0]
    assert first.key == second.key
    assert [source.source for source in first.sources] == ["KARABAS", "Teatr.org.ua"]
    assert [source.source for source in second.sources] == ["KARABAS", "Teatr.org.ua"]


def test_different_events_remain_separate():
    first = event("k1", "Я бачу, вас цікавить пітьма", "https://karabas.com/1")
    second = event("k2", "Хор Гомін", "https://karabas.com/2")
    assert len(build_canonical_events({"KARABAS": [first, second]})) == 2


def test_aware_and_naive_datetimes_can_be_compared():
    naive = event("k1", "Я бачу, вас цікавить пітьма", "https://karabas.com/1", datetime(2026, 10, 8, 18, 0))
    aware = event("t1", "Я бачу, вас цікавить пітьма", "https://teatr.org.ua/1", datetime(2026, 10, 8, 18, 0, tzinfo=timezone.utc))
    result = build_canonical_events({"KARABAS": [naive], "Teatr.org.ua": [aware]})
    assert len(result) == 1
    assert len(result[0].sources) == 2


def test_embedded_date_in_title_does_not_create_duplicate():
    first = event("k1", "Лос Янковерс. Колумбійці, які співають українські пісні", "https://karabas.com/1", datetime(2026, 9, 9, 18, 0))
    second = event("t1", "Лос Янковерс. Колумбійці, які співають українські пісні 9 вересня 2026 18:00", "https://teatr.org.ua/1", datetime(2026, 9, 9, 18, 0))
    result = build_canonical_events({"KARABAS": [first], "Teatr.org.ua": [second]})
    assert len(result) == 1
    assert result[0].title == "Лос Янковерс. Колумбійці, які співають українські пісні"
    assert len(result[0].sources) == 2


def test_appended_source_metadata_does_not_create_duplicate():
    first = event("k1", "Chico & Qatoshi x TIK | День Незалежності", "https://karabas.com/1", datetime(2026, 8, 22, 16, 0))
    second = event("t1", "Chico & Qatoshi x TIK | День Незалежності 22 серпня 2026 16:00 Тернопіль Агроленд від 600₴ Квитки", "https://teatr.org.ua/1", datetime(2026, 8, 22, 16, 0))
    result = build_canonical_events({"KARABAS": [first], "Teatr.org.ua": [second]})
    assert len(result) == 1
    assert len(result[0].sources) == 2


def test_same_event_at_two_times_remains_two_canonical_events():
    first = event("k16", "ТІК. Найкраще", "https://karabas.com/16", datetime(2026, 8, 22, 16, 0))
    second = event("k19", "ТІК. Найкраще", "https://karabas.com/19", datetime(2026, 8, 22, 19, 0))
    result = build_canonical_events({"KARABAS": [first, second]})
    assert len(result) == 2
    assert [item.start_at.hour for item in result] == [16, 19]


def test_real_production_duplicate_fixture_forms_three_canonical_events():
    fixture_path = Path(__file__).parent / "fixtures" / "canonical_duplicates_oct_2026.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    events_by_source: dict[str, list[RawEvent]] = {}
    for source, records in fixture.items():
        events_by_source[source] = [
            RawEvent(
                external_id=record["external_id"],
                title=record["title"],
                category="theatre",
                start_at=datetime.fromisoformat(record["start_at"]),
                venue=record["venue"],
                address="Тернопіль",
                price_text=None,
                ticket_url=f"https://example.com/{record['external_id']}",
                source_url=f"https://example.com/{source}/{record['external_id']}",
            )
            for record in records
        ]
    result = build_canonical_events(events_by_source)
    assert len(result) == 3
    assert sorted(len(canonical.sources) for canonical in result) == [2, 2, 2]
    assert {canonical.title for canonical in result} == {"Я бачу, вас цікавить пітьма", "Хор «Гомін»", "Я, «Побєда» і Берлін"}
