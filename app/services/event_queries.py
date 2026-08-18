from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Event
from app.services.event_identity import (
    normalize_title,
    title_variant_match,
    title_without_embedded_datetime,
    venue_variant_match,
)


@dataclass(slots=True)
class CanonicalDbEvent:
    representative: Event
    sources: list[Event]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _match_title(value: str) -> str:
    return normalize_title(title_without_embedded_datetime(value))


def _same_occurrence(a: Event, b: Event, time_tolerance_minutes: int = 15) -> bool:
    """Match source variants only when they describe the same occurrence."""
    if a.start_at is None or b.start_at is None:
        return False
    if abs((_utc(a.start_at) - _utc(b.start_at)).total_seconds()) > time_tolerance_minutes * 60:
        return False

    if not title_variant_match(a.title, b.title):
        return False

    venue_a = normalize_title(a.venue.name if a.venue else "")
    venue_b = normalize_title(b.venue.name if b.venue else "")
    if venue_a and venue_b and not venue_variant_match(venue_a, venue_b):
        return False

    return True


def events_for_day(session: Session, day: datetime) -> list[Event]:
    start = _utc(day.replace(hour=0, minute=0, second=0, microsecond=0))
    end = start + timedelta(days=1)
    query = (
        select(Event)
        .options(selectinload(Event.venue))
        .where(Event.start_at >= start, Event.start_at < end, Event.status == "active")
        .order_by(Event.start_at, Event.title)
    )
    return list(session.scalars(query).all())


def canonicalize_db_events(events: list[Event]) -> list[CanonicalDbEvent]:
    """Collapse duplicate source records but keep every distinct occurrence/time.

    Matching is against every existing member of a cluster rather than only its
    representative. This makes canonicalization stable when three or more
    sources contain slightly different title/venue variants of one occurrence.
    """
    clusters: list[list[Event]] = []

    for event in events:
        matched_cluster: list[Event] | None = None
        for cluster in clusters:
            if any(
                event.group_key == member.group_key
                and event.start_at is not None
                and member.start_at is not None
                and abs((_utc(event.start_at) - _utc(member.start_at)).total_seconds()) <= 15 * 60
                for member in cluster
            ) or any(_same_occurrence(event, member) for member in cluster):
                matched_cluster = cluster
                break

        if matched_cluster is None:
            clusters.append([event])
        else:
            matched_cluster.append(event)

    result: list[CanonicalDbEvent] = []
    for members in clusters:
        representative = sorted(
            members,
            key=lambda event: (
                event.start_at or datetime.max,
                -len(_match_title(event.title)),
                event.source_id,
            ),
        )[0]
        result.append(CanonicalDbEvent(representative=representative, sources=members))

    return sorted(
        result,
        key=lambda item: (item.representative.start_at or datetime.max, item.representative.title),
    )


def canonical_events_for_day(session: Session, day: datetime) -> list[CanonicalDbEvent]:
    events = events_for_day(session, day)
    canonical = canonicalize_db_events(events)
    return canonical


def canonical_events_for_range(
    session: Session, start: datetime, end: datetime
) -> list[CanonicalDbEvent]:
    start = _utc(start)
    end = _utc(end)
    query = (
        select(Event)
        .options(selectinload(Event.venue))
        .where(Event.start_at >= start, Event.start_at < end, Event.status == "active")
        .order_by(Event.start_at, Event.title)
    )
    events = list(session.scalars(query).all())
    canonical = canonicalize_db_events(events)
    return canonical


def category_counts(session: Session, start: datetime, end: datetime) -> list[tuple[str, int]]:
    """Count distinct displayed occurrences, not raw source rows."""
    events = canonical_events_for_range(session, start, end)
    counts = Counter((item.representative.category or "Інше") for item in events)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def canonical_events_for_category(
    session: Session, category: str, start: datetime, end: datetime
) -> list[CanonicalDbEvent]:
    start = _utc(start)
    end = _utc(end)
    query = (
        select(Event)
        .options(selectinload(Event.venue))
        .where(
            Event.start_at >= start,
            Event.start_at < end,
            Event.status == "active",
        )
        .order_by(Event.start_at, Event.title)
    )
    events = list(session.scalars(query).all())
    canonical = canonicalize_db_events(events)
    return [
        item
        for item in canonical
        if (item.representative.category or "Інше") == category
    ]
