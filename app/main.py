import asyncio

from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.config import settings
from app.db.session import init_db


async def run_bot():
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    init_db()
    asyncio.run(run_bot())
