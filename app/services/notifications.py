from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import Event
from app.db.user_models import NotificationPreference, TelegramUser


def users_for_tomorrow(session):
    return list(
        session.scalars(
            select(TelegramUser)
            .join(NotificationPreference, NotificationPreference.user_id == TelegramUser.id)
            .where(NotificationPreference.daily_tomorrow.is_(True))
        ).all()
    )


def tomorrow_events(session, now: datetime | None = None) -> list[Event]:
    now = now or datetime.now()
    start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return list(
        session.scalars(
            select(Event)
            .where(Event.start_at >= start, Event.start_at < end, Event.status == "active")
            .order_by(Event.start_at, Event.title)
        ).unique().all()
    )
