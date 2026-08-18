import asyncio
from datetime import datetime, timezone

from aiogram import Bot

from app.db.session import SessionLocal
from app.services.notifications import due_notifications, format_notification, mark_notified

POLL_INTERVAL_SECONDS = 60


async def async_process_due_notifications(bot: Bot, now: datetime | None = None) -> int:
    """Send due favorite reminders and persist delivery state after success."""
    current = now or datetime.now(timezone.utc)
    sent = 0
    with SessionLocal() as session:
        due = due_notifications(session, current)
        for subscription, item in due:
            telegram_id = subscription.user.telegram_id
            await bot.send_message(
                telegram_id,
                format_notification(item),
                disable_web_page_preview=True,
            )
            mark_notified(session, subscription, current)
            sent += 1
    return sent


async def notification_loop(bot: Bot, stop_event: asyncio.Event) -> None:
    """Continuously deliver favorite reminders while the application is running."""
    while not stop_event.is_set():
        try:
            await async_process_due_notifications(bot)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Notification worker failed: {exc!r}")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass
