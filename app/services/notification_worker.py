import asyncio
from datetime import datetime
from typing import Protocol

from aiogram import Bot
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.notifications import due_notifications, format_notification, mark_notified


class MessageSender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> object: ...


async def deliver_due_notifications(session: Session, sender: MessageSender, now: datetime) -> int:
    """Deliver due notifications and mark them only after Telegram delivery succeeds."""
    delivered = 0
    for subscription, item in due_notifications(session, now):
        user = subscription.user
        if user is None:
            continue
        await sender.send_message(user.telegram_id, format_notification(item))
        mark_notified(session, subscription, now)
        delivered += 1
    return delivered


async def notification_worker(bot: Bot, interval_seconds: int = 60) -> None:
    while True:
        try:
            now = datetime.now()
            with SessionLocal() as session:
                try:
                    await deliver_due_notifications(session, bot, now)
                except Exception:
                    session.rollback()
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)
