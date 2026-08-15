import asyncio
from datetime import datetime

from aiogram import Bot

from app.db.session import SessionLocal
from app.services.notifications import due_notifications, format_notification, mark_notified


async def notification_worker(bot: Bot, interval_seconds: int = 60) -> None:
    while True:
        try:
            now = datetime.now()
            with SessionLocal() as session:
                due = due_notifications(session, now)
                for subscription, item in due:
                    user = subscription.user
                    try:
                        await bot.send_message(user.telegram_id, format_notification(item))
                    except Exception:
                        continue
                    mark_notified(session, subscription, now)
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)
