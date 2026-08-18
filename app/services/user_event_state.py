from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Event
from app.services.event_queries import canonicalize_db_events


def related_group_keys(session: Session, group_key: str) -> set[str]:
    """Return all source group keys belonging to the same canonical occurrence."""
    seed = session.scalar(
        select(Event)
        .options(selectinload(Event.venue))
        .where(Event.group_key == group_key)
        .order_by(Event.start_at.asc(), Event.id.asc())
    )
    if seed is None or seed.start_at is None:
        return {group_key}

    window_start = seed.start_at - timedelta(minutes=15)
    window_end = seed.start_at + timedelta(minutes=15)
    candidates = list(
        session.scalars(
            select(Event)
            .options(selectinload(Event.venue))
            .where(
                Event.status == "active",
                Event.start_at >= window_start,
                Event.start_at <= window_end,
            )
        ).all()
    )
    for item in canonicalize_db_events(candidates):
        if any(source.id == seed.id for source in item.sources):
            return {source.group_key for source in item.sources}
    return {group_key}
