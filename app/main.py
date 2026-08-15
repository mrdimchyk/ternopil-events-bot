import asyncio

from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.config import settings
from app.db.session import init_db
from app.services.notification_worker import notification_worker


async def run_bot():
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    worker = asyncio.create_task(notification_worker(bot))
    try:
        await dp.start_polling(bot)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        await bot.session.close()


if __name__ == "__main__":
    init_db()
    asyncio.run(run_bot())
