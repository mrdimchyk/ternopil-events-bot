from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
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
    return canonicalize_db_events(events_for_day(session, day))


def canonical_events_for_range(session: Session, start: datetime, end: datetime) -> list[CanonicalDbEvent]:
    events = list(
        session.scalars(
            select(Event)
            .options(selectinload(Event.venue))
            .where(Event.start_at >= start, Event.start_at < end, Event.status == "active")
            .order_by(Event.start_at, Event.title)
        ).all()
    )
    return canonicalize_db_events(events)


def category_counts(session: Session, start: datetime, end: datetime) -> list[tuple[str, int]]:
    rows = session.execute(
        select(func.coalesce(Event.category, "Інше"), func.count(func.distinct(Event.group_key)))
        .where(Event.start_at >= start, Event.start_at < end, Event.status == "active")
        .group_by(func.coalesce(Event.category, "Інше"))
        .order_by(func.count(func.distinct(Event.group_key)).desc())
    ).all()
    return [(str(category), int(count)) for category, count in rows]


def canonical_events_for_category(
    session: Session, category: str, start: datetime, end: datetime
) -> list[CanonicalDbEvent]:
    events = list(
        session.scalars(
            select(Event)
            .options(selectinload(Event.venue))
            .where(
                Event.start_at >= start,
                Event.start_at < end,
                Event.status == "active",
                func.coalesce(Event.category, "Інше") == category,
            )
            .order_by(Event.start_at, Event.title)
        ).all()
    )
    return canonicalize_db_events(events)
