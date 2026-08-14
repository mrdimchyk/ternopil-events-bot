from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Event, EventChange
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


@dataclass(slots=True)
class NotificationItem:
    event_id: int
    title: str
    start_at: datetime | None
    venue: str | None
    price_text: str | None
    ticket_url: str | None


def get_ticket_sale_notifications(
    session: Session,
    since: datetime,
) -> list[NotificationItem]:
    changes = session.scalars(
        select(EventChange)
        .where(
            EventChange.change_type == "ticket_sale_started",
            EventChange.detected_at >= since,
        )
        .options(joinedload(EventChange.event).joinedload(Event.venue))
        .order_by(EventChange.detected_at.asc())
    ).all()

    result: list[NotificationItem] = []
    seen: set[int] = set()

    for change in changes:
        event = change.event
        if event.id in seen:
            continue
        seen.add(event.id)
        result.append(
            NotificationItem(
                event_id=event.id,
                title=event.title,
                start_at=event.start_at,
                venue=event.venue.name if event.venue else None,
                price_text=event.price_text,
                ticket_url=event.ticket_url,
            )
        )

    return result


def format_ticket_sale_notification(item: NotificationItem) -> str:
    lines = [
        "🎟️ <b>Почався продаж квитків!</b>",
        "",
        f"<b>{item.title}</b>",
    ]

    if item.start_at:
        lines.append(f"📅 {item.start_at.strftime('%d.%m.%Y о %H:%M')}")
    if item.venue:
        lines.append(f"📍 {item.venue}")
    if item.price_text:
        lines.append(f"💰 {item.price_text}")
    if item.ticket_url:
        lines.extend(["", f'🎫 <a href="{item.ticket_url}">Купити квиток</a>'])

    return "\n".join(lines)
