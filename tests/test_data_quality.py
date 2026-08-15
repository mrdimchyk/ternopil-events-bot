from datetime import datetime, timezone

from app.collectors.base import RawEvent
from app.services.data_quality import find_duplicate_candidates, validate_events


def make_event(
    external_id: str = "id-1",
    title: str = "Imagine Dragons",
    start_at: datetime | None = None,
    source_url: str = "https://example.com/event",
) -> RawEvent:
    return RawEvent(
        external_id=external_id,
        title=title,
        category=None,
        start_at=start_at or datetime(2026, 10, 8, 19, 0),
        venue="Театр",
        address="Тернопіль",
        price_text="500 грн",
        ticket_url="https://example.com/tickets",
        source_url=source_url,
    )


def test_quality_accepts_valid_future_event():
    event = make_event()
    issues = validate_events(
        "KARABAS",
        [event],
        now=datetime(2026, 8, 15, tzinfo=timezone.utc),
    )
    assert issues == []


def test_quality_rejects_past_event_and_missing_title():
    event = make_event(start_at=datetime(2026, 8, 14, 19, 0), title="")
    issues = validate_events(
        "Teatr.org.ua",
        [event],
        now=datetime(2026, 8, 15, tzinfo=timezone.utc),
    )
    assert {issue.code for issue in issues} == {"missing_title", "past_event"}


def test_quality_rejects_invalid_source_url():
    event = make_event(source_url="not-a-url")
    issues = validate_events("Concert.ua", [event])
    assert any(issue.code == "invalid_source_url" for issue in issues)


def test_cross_source_duplicate_candidate_matches_normalized_title_and_time():
    start = datetime(2026, 10, 8, 19, 0)
    first = make_event("karabas-1", "Imagine Dragons", start)
    second = make_event("concert-1", "imagine dragons!", datetime(2026, 10, 8, 19, 10))

    candidates = find_duplicate_candidates({"KARABAS": [first], "Concert.ua": [second]})

    assert len(candidates) == 1
    assert candidates[0].sources == ("Concert.ua", "KARABAS")


def test_cross_source_duplicate_does_not_match_different_titles():
    start = datetime(2026, 10, 8, 19, 0)
    first = make_event("karabas-1", "Imagine Dragons", start)
    second = make_event("concert-1", "Robbie Williams", start)

    assert find_duplicate_candidates({"KARABAS": [first], "Concert.ua": [second]}) == []
