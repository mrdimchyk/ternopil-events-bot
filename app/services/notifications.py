from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db.models import Event, EventChange
from app.db.user_models import FavoriteNotification, TelegramUser
from app.services.user_event_state import related_group_keys

DEFAULT_NOTIFY_BEFORE_MINUTES = 24 * 60


def _utc_naive(value: datetime) -> datetime:
    """Normalize aware/naive datetimes to naive UTC for internal comparisons."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


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
    keys = related_group_keys(session, group_key)
    subscriptions = session.scalars(
        select(FavoriteNotification).where(
            FavoriteNotification.user_id == user.id,
            FavoriteNotification.group_key.in_(keys),
        )
    ).all()
    if not subscriptions:
        return False
    for subscription in subscriptions:
        session.delete(subscription)
    session.commit()
    return True


def notification_group_keys(session: Session, telegram_id: int) -> set[str]:
    """Return raw enabled subscription keys; canonicalize only when listing events."""
    user = session.scalar(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))
    if user is None:
        return set()
    return set(
        session.scalars(
            select(FavoriteNotification.group_key).where(
                FavoriteNotification.user_id == user.id,
                FavoriteNotification.enabled.is_(True),
            )
        ).all()
    )


def tomorrow_events(session: Session, now: datetime | None = None) -> list[Event]:
    """Return unique active events occurring tomorrow in the configured city timezone."""
    current = now or datetime.now(timezone.utc)
    timezone_info = ZoneInfo(settings.timezone)
    local_now = current.astimezone(timezone_info) if current.tzinfo else current.replace(tzinfo=timezone_info)
    tomorrow = local_now.date() + timedelta(days=1)
    start_local = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone_info)
    end_local = start_local + timedelta(days=1)

    events = session.scalars(
        select(Event)
        .options(joinedload(Event.venue))
        .where(
            Event.status == "active",
            Event.start_at >= start_local,
            Event.start_at < end_local,
        )
        .order_by(Event.start_at.asc(), Event.id.asc())
    ).all()

    unique: list[Event] = []
    seen_groups: set[str] = set()
    for event in events:
        if event.group_key in seen_groups:
            continue
        seen_groups.add(event.group_key)
        unique.append(event)
    return unique


def due_notifications(session: Session, now: datetime) -> list[tuple[FavoriteNotification, NotificationItem]]:
    now_utc = _utc_naive(now)
    rows = session.scalars(select(FavoriteNotification).where(FavoriteNotification.enabled.is_(True))).all()
    result = []
    for subscription in rows:
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
        event_start = _utc_naive(event.start_at)
        target = event_start - timedelta(minutes=subscription.notify_before_minutes)
        last_notified = _utc_naive(subscription.last_notified_at) if subscription.last_notified_at is not None else None
        if target > now_utc or (last_notified is not None and last_notified >= target):
            continue
        result.append((subscription, NotificationItem(event.id, event.group_key, event.title, event_start, event.venue.name if event.venue else None, event.price_text, event.ticket_url)))
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
