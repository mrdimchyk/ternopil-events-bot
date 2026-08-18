from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher

from app.collectors.base import RawEvent
from app.services.event_identity import (
    make_group_key,
    normalize_title,
    title_variant_match,
    title_without_embedded_datetime,
    venue_variant_match,
)


@dataclass(slots=True)
class CanonicalSource:
    source: str
    external_id: str
    source_url: str
    ticket_url: str | None
    price_text: str | None


@dataclass(slots=True)
class CanonicalEvent:
    key: str
    title: str
    start_at: datetime | None
    venue: str | None
    address: str | None
    category: str | None
    description: str | None
    sources: list[CanonicalSource]


def _comparison_time(value: datetime) -> datetime:
    """Normalize naive/aware datetimes to naive UTC for safe comparison."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _same_event(a: RawEvent, b: RawEvent, time_tolerance_minutes: int = 15) -> bool:
    if a.start_at is None or b.start_at is None:
        return False
    delta = _comparison_time(a.start_at) - _comparison_time(b.start_at)
    if abs(delta.total_seconds()) > time_tolerance_minutes * 60:
        return False

    if not title_variant_match(a.title, b.title):
        return False

    venue_a = normalize_title(a.venue or "")
    venue_b = normalize_title(b.venue or "")
    if venue_a and venue_b and not venue_variant_match(venue_a, venue_b):
        return False

    return True


def build_canonical_events(events_by_source: dict[str, list[RawEvent]]) -> list[CanonicalEvent]:
    clusters: list[list[tuple[str, RawEvent]]] = []

    for source, events in events_by_source.items():
        for event in events:
            for cluster in clusters:
                if _same_event(event, cluster[0][1]):
                    cluster.append((source, event))
                    break
            else:
                clusters.append([(source, event)])

    result: list[CanonicalEvent] = []
    for cluster in clusters:
        ordered = sorted(cluster, key=lambda item: (len(item[1].title), item[1].title), reverse=True)
        representative = ordered[0][1]
        start_at = min(
            (event.start_at for _, event in cluster if event.start_at is not None),
            key=_comparison_time,
            default=None,
        )
        key_basis = make_group_key(representative.title, start_at, representative.venue)

        result.append(
            CanonicalEvent(
                key=key_basis,
                title=title_without_embedded_datetime(representative.title),
                start_at=start_at,
                venue=representative.venue,
                address=representative.address,
                category=representative.category,
                description=representative.description,
                sources=[
                    CanonicalSource(
                        source=source,
                        external_id=event.external_id,
                        source_url=event.source_url,
                        ticket_url=event.ticket_url,
                        price_text=event.price_text,
                    )
                    for source, event in sorted(cluster, key=lambda item: item[0])
                ],
            )
        )

    return result
