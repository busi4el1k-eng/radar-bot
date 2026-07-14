"""Punctul de intrare al botului RADAR — long polling."""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import db
import handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("radar")


async def main() -> None:
    required = ["BOT_TOKEN", "CHANNEL_ID", "ADMIN_IDS", "DATABASE_URL"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        logger.error(
            "Lipsesc variabile de mediu: %s. Rulează mai întâi: python setup.py",
            ", ".join(missing),
        )
        sys.exit(1)

    await db.init(os.environ["DATABASE_URL"])

    bot = Bot(
        token=os.environ["BOT_TOKEN"],
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(handlers.admin_router)
    dp.include_router(handlers.user_router)

    me = await bot.get_me()
    logger.info("Bot pornit: @%s — aștept mesaje (long polling).", me.username)
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot oprit.")
