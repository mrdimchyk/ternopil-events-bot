import asyncio
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from sqlalchemy import text

from app.bot.handlers import router
from app.config import settings
from app.db.session import SessionLocal, init_db


async def run_webhook_app() -> web.Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    bot = Bot(
        settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    base_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base_url:
        hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
        if hostname:
            base_url = f"https://{hostname}"

    webhook_path = f"/telegram/{settings.telegram_bot_token}"
    webhook_url = f"{base_url}{webhook_path}" if base_url else ""

    async def on_shutdown(_app: web.Application) -> None:
        polling_task = _app.get("polling_task")
        if polling_task:
            polling_task.cancel()
            await asyncio.gather(polling_task, return_exceptions=True)
        await bot.session.close()

    async def health(_request: web.Request) -> web.Response:
        """Report readiness only after database initialization has completed."""
        if not _request.app.get("runtime_ready", False):
            return web.json_response(
                {"status": "starting", "database": "initializing"},
                status=503,
            )
        try:
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
        except Exception as exc:
            return web.json_response(
                {"status": "degraded", "database": "unavailable", "error": type(exc).__name__},
                status=503,
            )
        return web.json_response({"status": "ok", "database": "ok"})

    app = web.Application()
    app["runtime_ready"] = False
    app["bot"] = bot
    app["dispatcher"] = dp
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    if webhook_url:
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
    else:
        async def start_polling() -> None:
            await bot.delete_webhook(drop_pending_updates=False)
            await dp.start_polling(bot, handle_signals=False)

        app["polling_task_factory"] = start_polling

    setup_application(app, dp, bot=bot)
    return app


async def initialize_runtime(app: web.Application) -> None:
    """Initialize slow dependencies after the HTTP port is already listening."""
    bot: Bot = app["bot"]
    dp: Dispatcher = app["dispatcher"]
    base_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base_url:
        hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
        if hostname:
            base_url = f"https://{hostname}"

    try:
        await asyncio.to_thread(init_db)
        if base_url:
            webhook_path = f"/telegram/{settings.telegram_bot_token}"
            webhook_url = f"{base_url}{webhook_path}"
            await bot.set_webhook(
                webhook_url,
                allowed_updates=dp.resolve_used_update_types(),
            )
            print(f"Telegram webhook configured: {webhook_url}")
        else:
            polling_task = asyncio.create_task(
                bot.delete_webhook(drop_pending_updates=False)
            )
            await polling_task
            polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
            app["polling_task"] = polling_task
            print("Telegram polling started (no public Render URL detected)")
        app["runtime_ready"] = True
        print("Runtime initialization complete")
    except Exception as exc:
        app["runtime_error"] = repr(exc)
        print(f"Runtime initialization failed: {exc!r}")


async def main() -> None:
    application = await run_webhook_app()
    runner = web.AppRunner(application)
    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000")),
        shutdown_timeout=30,
    )
    await site.start()
    print(f"HTTP server listening on 0.0.0.0:{os.getenv('PORT', '10000')}")

    # Do not block port binding on DB migrations or Telegram setup.
    await initialize_runtime(application)

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
