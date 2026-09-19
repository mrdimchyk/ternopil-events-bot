from dataclasses import dataclass

from app.collectors.base import RawEvent


@dataclass(slots=True)
class SourceFieldCoverage:
    event_count: int
    start_at_ratio: float
    venue_ratio: float
    address_ratio: float
    price_ratio: float
    ticket_url_ratio: float
    description_ratio: float


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _ratio(events: list[RawEvent], field: str) -> float:
    if not events:
        return 0.0
    present = sum(1 for event in events if _present(getattr(event, field)))
    return present / len(events)


def source_field_coverage(
    events_by_source: dict[str, list[RawEvent]],
    source_names: list[str],
) -> dict[str, SourceFieldCoverage]:
    """Measure data richness without turning optional fields into quality gates."""
    result: dict[str, SourceFieldCoverage] = {}
    for source in source_names:
        events = events_by_source.get(source, [])
        result[source] = SourceFieldCoverage(
            event_count=len(events),
            start_at_ratio=_ratio(events, "start_at"),
            venue_ratio=_ratio(events, "venue"),
            address_ratio=_ratio(events, "address"),
            price_ratio=_ratio(events, "price_text"),
            ticket_url_ratio=_ratio(events, "ticket_url"),
            description_ratio=_ratio(events, "description"),
        )
    return result
