import asyncio
import logging
from datetime import datetime
from typing import Protocol

from aiogram import Bot
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.notifications import due_notifications, format_notification, mark_notified


logger = logging.getLogger(__name__)


class MessageSender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> object: ...


async def deliver_due_notifications(session: Session, sender: MessageSender, now: datetime) -> int:
    """Deliver due notifications and mark them only after Telegram delivery succeeds."""
    delivered = 0
    for subscription, item in due_notifications(session, now):
        user = subscription.user
        if user is None:
            logger.warning("Skipping notification %s: user is missing", subscription.id)
            continue
        await sender.send_message(user.telegram_id, format_notification(item))
        mark_notified(session, subscription, now)
        delivered += 1
    return delivered


async def notification_worker(bot: Bot, interval_seconds: int = 60) -> None:
    """Continuously deliver due notifications until the bot is shut down.

    Delivery errors are isolated to the current polling cycle so one bad
    Telegram request cannot terminate the worker. Cancellation is propagated
    so the task can shut down cleanly with the bot.
    """
    while True:
        try:
            now = datetime.now()
            with SessionLocal() as session:
                try:
                    delivered = await deliver_due_notifications(session, bot, now)
                    if delivered:
                        logger.info("Notification worker delivered %d notification(s)", delivered)
                except Exception:
                    session.rollback()
                    logger.exception("Notification delivery cycle failed")
        except asyncio.CancelledError:
            logger.info("Notification worker stopped")
            raise
        except Exception:
            logger.exception("Notification worker cycle failed")
        await asyncio.sleep(interval_seconds)
