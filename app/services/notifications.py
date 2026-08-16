from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Event, EventChange
from app.db.user_models import FavoriteNotification, TelegramUser

DEFAULT_NOTIFY_BEFORE_MINUTES = 24 * 60


@dataclass(slots=True)
class NotificationItem:
    event_id: int
    group_key: str
    title: str
    start_at: datetime | None
    venue: str | None
    price_text: str | None
    ticket_url: str | None


def subscribe_favorite(session: Session, telegram_id: int, group_key: str, notify_before_minutes: int = DEFAULT_NOTIFY_BEFORE_MINUTES) -> bool:
    user = session.scalar(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))
    if user is None:
        user = TelegramUser(telegram_id=telegram_id)
        session.add(user)
        session.flush()
    existing = session.scalar(select(FavoriteNotification).where(FavoriteNotification.user_id == user.id, FavoriteNotification.group_key == group_key))
    if existing:
        existing.enabled = True
        existing.notify_before_minutes = notify_before_minutes
        existing.last_notified_at = None
        session.commit()
        return False
    session.add(FavoriteNotification(user_id=user.id, group_key=group_key, notify_before_minutes=notify_before_minutes, enabled=True))
    session.commit()
    return True


def unsubscribe_favorite(session: Session, telegram_id: int, group_key: str) -> bool:
    user = session.scalar(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))
    if user is None:
        return False
    subscription = session.scalar(select(FavoriteNotification).where(FavoriteNotification.user_id == user.id, FavoriteNotification.group_key == group_key))
    if subscription is None:
        return False
    session.delete(subscription)
    session.commit()
    return True


def notification_group_keys(session: Session, telegram_id: int) -> set[str]:
    user = session.scalar(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))
    if user is None:
        return set()
    return set(session.scalars(select(FavoriteNotification.group_key).where(FavoriteNotification.user_id == user.id, FavoriteNotification.enabled.is_(True))).all())


def due_notifications(session: Session, now: datetime) -> list[tuple[FavoriteNotification, NotificationItem]]:
    rows = session.scalars(select(FavoriteNotification).where(FavoriteNotification.enabled.is_(True))).all()
    result = []
    for subscription in rows:
        # A canonical group may have one Event row per source. Never use
        # Session.scalar() here: multiple physical events for the same
        # group_key are expected in a multi-source database.
        event = session.scalars(
            select(Event)
            .options(joinedload(Event.venue))
            .where(
                Event.group_key == subscription.group_key,
                Event.status == "active",
                Event.start_at >= now,
            )
            .order_by(Event.start_at.asc(), Event.id.asc())
        ).first()
        if event is None or event.start_at is None:
            continue
        target = event.start_at - timedelta(minutes=subscription.notify_before_minutes)
        if target > now or (subscription.last_notified_at is not None and subscription.last_notified_at >= target):
            continue
        result.append((subscription, NotificationItem(event.id, event.group_key, event.title, event.start_at, event.venue.name if event.venue else None, event.price_text, event.ticket_url)))
    return result


def mark_notified(session: Session, subscription: FavoriteNotification, now: datetime) -> None:
    subscription.last_notified_at = now
    session.commit()


def get_ticket_sale_notifications(session: Session, since: datetime) -> list[NotificationItem]:
    changes = session.scalars(select(EventChange).where(EventChange.change_type == "ticket_sale_started", EventChange.detected_at >= since).options(joinedload(EventChange.event).joinedload(Event.venue)).order_by(EventChange.detected_at.asc())).all()
    result = []
    seen: set[int] = set()
    for change in changes:
        event = change.event
        if event.id in seen:
            continue
        seen.add(event.id)
        result.append(NotificationItem(event.id, event.group_key, event.title, event.start_at, event.venue.name if event.venue else None, event.price_text, event.ticket_url))
    return result


def format_notification(item: NotificationItem) -> str:
    lines = ["🔔 <b>Нагадування про подію</b>", "", f"<b>{item.title}</b>"]
    if item.start_at:
        lines.append(f"📅 {item.start_at.strftime('%d.%m.%Y о %H:%M')}")
    if item.venue:
        lines.append(f"📍 {item.venue}")
    if item.price_text:
        lines.append(f"💰 {item.price_text}")
    if item.ticket_url:
        lines.extend(["", f'🎫 <a href="{item.ticket_url}">Купити квиток</a>'])
    return "\n".join(lines)
