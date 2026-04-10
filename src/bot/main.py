"""HOFIZ BOT — Asosiy entry point."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from src.common.config import settings
from src.bot.services.redis_service import RedisService
from src.db.engine import engine
from src.db.models import Base

# Handlers
from src.bot.handlers import start, media_download, music_recognition, inline_mode, subscription, admin

# Middlewares
from src.bot.middlewares.logging_mw import LoggingMiddleware
from src.bot.middlewares.rate_limit import RateLimitMiddleware
from src.bot.middlewares.subscription import SubscriptionCheckMiddleware
from src.bot.middlewares.user_reg import UserRegistrationMiddleware

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("hofiz.main")


async def on_startup(bot: Bot) -> None:
    """Bot ishga tushganda."""
    logger.info("⚡️ HOFIZ BOT ishga tushmoqda...")

    # Redis ulash
    await RedisService.connect()
    logger.info("✅ Redis ulandi")

    # DB jadvallarini yaratish (agar mavjud bo'lmasa)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tayyor")

    # Webhook sozlash
    if settings.bot_mode == "webhook" and settings.bot_webhook_url:
        await bot.set_webhook(
            url=f"{settings.bot_webhook_url}/webhook",
            secret_token=settings.bot_webhook_secret,
            drop_pending_updates=True,
        )
        logger.info("✅ Webhook sozlandi: %s", settings.bot_webhook_url)
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Long-polling rejimi")

    me = await bot.get_me()
    logger.info("🤖 Bot: @%s (ID: %s)", me.username, me.id)


async def on_shutdown(bot: Bot) -> None:
    """Bot to'xtayotganda."""
    logger.info("🛑 HOFIZ BOT to'xtamoqda...")

    # Music service yopish
    from src.bot.services.music_service import music_service
    await music_service.close()

    # Download service yopish
    from src.bot.services.download_service import download_service
    await download_service.close()

    # Redis yopish
    await RedisService.close()

    # DB yopish
    await engine.dispose()

    logger.info("👋 HOFIZ BOT to'xtadi")


def create_dispatcher() -> Dispatcher:
    """Dispatcher yaratish — routerlar va middleware'lar."""
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    # Startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Middleware'lar (tartib muhim!)
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(RateLimitMiddleware(max_requests=15, window=60))
    dp.message.middleware(UserRegistrationMiddleware())
    dp.message.middleware(SubscriptionCheckMiddleware())

    dp.callback_query.middleware(LoggingMiddleware())
    dp.callback_query.middleware(UserRegistrationMiddleware())
    dp.callback_query.middleware(SubscriptionCheckMiddleware())

    # Routerlar (tartib muhim — birinchi match ishlaydi!)
    dp.include_router(admin.router)           # /admin — admin buyruqlari
    dp.include_router(subscription.router)    # check_sub, req_channel callbacks
    dp.include_router(start.router)           # /start, /help
    dp.include_router(media_download.router)  # URL handlerlar
    dp.include_router(music_recognition.router)  # voice, audio, video, video_note
    dp.include_router(inline_mode.router)     # inline query

    return dp


def create_bot() -> Bot:
    """Bot instance yaratish."""
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def run_polling() -> None:
    """Long-polling rejimida ishga tushirish."""
    bot = create_bot()
    dp = create_dispatcher()
    await dp.start_polling(bot)


async def run_webhook() -> None:
    """Webhook rejimida ishga tushirish."""
    bot = create_bot()
    dp = create_dispatcher()

    app = web.Application()
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.bot_webhook_secret,
    )
    webhook_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()
    logger.info("🌐 Webhook server: 0.0.0.0:8080")

    # Cheksiz ishlash
    await asyncio.Event().wait()


def main() -> None:
    """Asosiy funksiya."""
    try:
        if settings.bot_mode == "webhook":
            asyncio.run(run_webhook())
        else:
            asyncio.run(run_polling())
    except Exception as e:
        print(f"FATAL ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
