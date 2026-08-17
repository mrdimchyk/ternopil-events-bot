import asyncio
import os
from datetime import datetime, timezone

from aiogram import Bot

from app.db.session import SessionLocal
from app.services.notification_worker import deliver_due_notifications


async def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    now = datetime.now(timezone.utc)
    bot = Bot(token)
    try:
        with SessionLocal() as session:
            delivered = await deliver_due_notifications(session, bot, now)
        print(f"Notification delivery cycle: delivered={delivered}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
