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
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat
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

    await setup_menu(bot)
    me = await bot.get_me()
    logger.info("Bot pornit: @%s — aștept mesaje (long polling).", me.username)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await db.close()


USER_COMMANDS = [
    BotCommand(command="start", description="🚀 Adaugă produsul tău"),
    BotCommand(command="cancel", description="❌ Anulează formularul curent"),
]

ADMIN_COMMANDS = USER_COMMANDS + [
    BotCommand(command="pending", description="🗂 Submisii în moderare"),
    BotCommand(command="inbox", description="📥 Răsfoiește itemele agregate"),
    BotCommand(command="pull", description="📡 Rulează agregatorul acum"),
    BotCommand(command="inboxstats", description="📊 Statistici inbox"),
]


async def setup_menu(bot: Bot) -> None:
    """Meniul de comenzi: unul simplu pentru toți, complet pentru admini."""
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    for admin_id in handlers.ADMIN_IDS:
        try:
            await bot.set_my_commands(
                ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except TelegramBadRequest as exc:
            logger.warning(
                "Nu am putut seta meniul pentru adminul %d: %s "
                "(adminul trebuie să fi pornit o conversație cu botul)",
                admin_id,
                exc,
            )


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
