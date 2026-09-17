from datetime import datetime

from app.services.canonical_events import CanonicalEvent, CanonicalSource
from app.services.source_value import source_value_metrics


def _source(name: str) -> CanonicalSource:
    return CanonicalSource(
        source=name,
        external_id=name,
        source_url=f"https://example.com/{name}",
        ticket_url=None,
        price_text=None,
    )


def _event(key: str, *sources: str) -> CanonicalEvent:
    return CanonicalEvent(
        key=key,
        title=key,
        start_at=datetime(2026, 9, 20, 18, 0),
        venue="Venue",
        address=None,
        category=None,
        description=None,
        sources=[_source(source) for source in sources],
    )


def test_source_value_metrics_measure_unique_and_overlap() -> None:
    metrics = source_value_metrics(
        [_event("one", "A"), _event("two", "A", "B"), _event("three", "B")],
        ["A", "B", "C"],
    )

    assert metrics["A"].canonical_events == 2
    assert metrics["A"].unique_events == 1
    assert metrics["A"].shared_events == 1
    assert metrics["A"].overlap_ratio == 0.5
    assert metrics["A"].unique_coverage_ratio == 1 / 3

    assert metrics["B"].canonical_events == 2
    assert metrics["B"].unique_events == 1
    assert metrics["B"].shared_events == 1

    assert metrics["C"].canonical_events == 0
    assert metrics["C"].unique_events == 0
    assert metrics["C"].overlap_ratio == 0.0
    assert metrics["C"].unique_coverage_ratio == 0.0
