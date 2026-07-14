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
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
import handlers
import handlers_inbox
import scraper
import texts

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
    dp.include_router(handlers_inbox.inbox_router)
    dp.include_router(handlers.user_router)

    # Pull automat la fiecare PULL_INTERVAL_HOURS ore (default 6), în același
    # proces — fără publicare automată, doar notificare către admini.
    interval_hours = int(os.getenv("PULL_INTERVAL_HOURS", "6"))
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_pull, "interval", hours=interval_hours, args=[bot])
    scheduler.start()
    logger.info("Pull automat programat la fiecare %d ore.", interval_hours)

    me = await bot.get_me()
    logger.info("Bot pornit: @%s — aștept mesaje (long polling).", me.username)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await db.close()


async def scheduled_pull(bot: Bot) -> None:
    report = await scraper.run_pull()
    if report is None or report.new == 0:
        return
    for admin_id in handlers.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, texts.SCRAPE_NOTIFY.format(n=report.new))
        except Exception as exc:
            logger.warning("Nu am putut notifica adminul %d: %s", admin_id, exc)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot oprit.")
