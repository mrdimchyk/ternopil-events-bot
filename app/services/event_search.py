from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Event
from app.services.event_queries import CanonicalDbEvent, canonicalize_db_events


def search_canonical_events(
    session: Session, query: str, start: datetime | None = None, limit: int = 20
) -> list[CanonicalDbEvent]:
    term = " ".join(query.split()).strip().lower()
    if not term:
        return []

    filters = [
        Event.status == "active",
        func.lower(Event.title).contains(term),
    ]
    if start is not None:
        filters.append(Event.start_at.is_(None) | (Event.start_at >= start))

    events = list(
        session.scalars(
            select(Event)
            .options(selectinload(Event.venue))
            .where(*filters)
            .order_by(Event.start_at, Event.title)
            .limit(limit * 3)
        ).all()
    )
    return canonicalize_db_events(events)[:limit]
