from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Event


@dataclass(slots=True)
class CanonicalDbEvent:
    representative: Event
    sources: list[Event]


def events_for_day(session: Session, day: datetime) -> list[Event]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return list(
        session.scalars(
            select(Event)
            .options(selectinload(Event.venue))
            .where(Event.start_at >= start, Event.start_at < end, Event.status == "active")
            .order_by(Event.start_at, Event.title)
        ).all()
    )


def canonicalize_db_events(events: list[Event]) -> list[CanonicalDbEvent]:
    """Collapse source records by group_key without dropping ticket offers."""
    groups: dict[str, list[Event]] = {}
    for event in events:
        groups.setdefault(event.group_key, []).append(event)

    result: list[CanonicalDbEvent] = []
    for members in groups.values():
        representative = sorted(
            members,
            key=lambda event: (
                event.start_at or datetime.max,
                -len(event.title),
                event.source_id,
            ),
        )[0]
        result.append(CanonicalDbEvent(representative=representative, sources=members))

    return sorted(
        result,
        key=lambda item: (item.representative.start_at or datetime.max, item.representative.title),
    )


def canonical_events_for_day(session: Session, day: datetime) -> list[CanonicalDbEvent]:
    """Return one display event per canonical group while preserving all source offers."""
    return canonicalize_db_events(events_for_day(session, day))
