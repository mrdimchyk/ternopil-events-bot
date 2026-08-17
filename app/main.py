import asyncio
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.bot.handlers import router
from app.config import settings
from app.db.session import init_db
from app.services.notification_worker import notification_worker


async def run_webhook_app() -> web.Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    base_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("RENDER_EXTERNAL_URL is not configured")

    webhook_path = f"/telegram/{settings.telegram_bot_token}"
    webhook_url = f"{base_url}{webhook_path}"
    worker_task: asyncio.Task | None = None

    async def on_startup(_app: web.Application) -> None:
        nonlocal worker_task
        await bot.set_webhook(
            webhook_url,
            allowed_updates=dp.resolve_used_update_types(),
        )
        worker_task = asyncio.create_task(notification_worker(bot))

    async def on_shutdown(_app: web.Application) -> None:
        if worker_task is not None:
            worker_task.cancel()
            await asyncio.gather(worker_task, return_exceptions=True)
        await bot.delete_webhook()
        await bot.session.close()

    async def health(_request: web.Request) -> web.Response:
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    setup_application(app, dp, bot=bot)
    return app


if __name__ == "__main__":
    init_db()
    application = asyncio.run(run_webhook_app())
    web.run_app(
        application,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000")),
        shutdown_timeout=30,
    )
