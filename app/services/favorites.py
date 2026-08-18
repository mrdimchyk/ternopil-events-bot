from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Event, Favorite
from app.services.event_queries import CanonicalDbEvent, canonicalize_db_events
from app.services.user_event_state import related_group_keys


def add_favorite(session: Session, user_id: int, group_key: str) -> bool:
    existing = session.scalar(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.group_key == group_key)
    )
    if existing:
        return False
    session.add(Favorite(user_id=user_id, group_key=group_key))
    session.commit()
    return True


def remove_favorite(session: Session, user_id: int, group_key: str) -> bool:
    keys = related_group_keys(session, group_key)
    favorites = session.scalars(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.group_key.in_(keys))
    ).all()
    if not favorites:
        return False
    for favorite in favorites:
        session.delete(favorite)
    session.commit()
    return True


def favorite_group_keys(session: Session, user_id: int) -> set[str]:
    rows = session.scalars(select(Favorite.group_key).where(Favorite.user_id == user_id)).all()
    expanded: set[str] = set()
    for key in rows:
        expanded.update(related_group_keys(session, key))
    return expanded


def favorite_events(session: Session, user_id: int, now: datetime) -> list[CanonicalDbEvent]:
    keys = favorite_group_keys(session, user_id)
    if not keys:
        return []
    events = list(
        session.scalars(
            select(Event)
            .options(selectinload(Event.venue))
            .where(
                Event.group_key.in_(keys),
                Event.start_at >= now,
                Event.status == "active",
            )
            .order_by(Event.start_at, Event.title)
        ).all()
    )
    return canonicalize_db_events(events)
