from datetime import datetime

from app.collectors.base import RawEvent
from app.services.source_field_coverage import source_field_coverage


def _event(**overrides) -> RawEvent:
    values = {
        "external_id": "event",
        "title": "Event",
        "category": "concert",
        "start_at": datetime(2026, 9, 20, 18, 0),
        "venue": "Venue",
        "address": "Address",
        "price_text": "300 грн",
        "ticket_url": "https://example.com/ticket",
        "source_url": "https://example.com/event",
        "description": "Description",
    }
    values.update(overrides)
    return RawEvent(**values)


def test_source_field_coverage_measures_optional_data_presence() -> None:
    metrics = source_field_coverage(
        {
            "A": [
                _event(external_id="one"),
                _event(
                    external_id="two",
                    address=None,
                    price_text="",
                    ticket_url=None,
                    description=None,
                ),
            ]
        },
        ["A", "B"],
    )

    assert metrics["A"].event_count == 2
    assert metrics["A"].start_at_ratio == 1.0
    assert metrics["A"].venue_ratio == 1.0
    assert metrics["A"].address_ratio == 0.5
    assert metrics["A"].price_ratio == 0.5
    assert metrics["A"].ticket_url_ratio == 0.5
    assert metrics["A"].description_ratio == 0.5

    assert metrics["B"].event_count == 0
    assert metrics["B"].venue_ratio == 0.0


def test_source_field_coverage_treats_blank_strings_as_missing() -> None:
    metrics = source_field_coverage(
        {"A": [_event(venue="   ", address="")]},
        ["A"],
    )

    assert metrics["A"].venue_ratio == 0.0
    assert metrics["A"].address_ratio == 0.0
