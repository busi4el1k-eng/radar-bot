"""Comenzile admin ale agregatorului: /pull, /inbox, /inboxstats + review-ul
item cu item (publică / editează / schimbă poza / ignoră / următorul)."""

import html
import json
import logging
import os

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
)

import db
import scraper
import texts
from handlers import ADMIN_IDS, CHANNEL_ID, _post_url
from sources import SOURCE_NAMES

logger = logging.getLogger(__name__)

inbox_router = Router(name="inbox")
inbox_router.message.filter(F.chat.type == "private", F.from_user.id.in_(ADMIN_IDS))
inbox_router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class InboxEdit(StatesGroup):
    description = State()
    photo = State()


POST_FOOTER = os.getenv("POST_FOOTER", "").strip()


def _source_name(slug: str) -> str:
    return SOURCE_NAMES.get(slug, slug)


def _format_stars(stars: int) -> str:
    if stars >= 1000:
        formatted = f"{stars / 1000:.1f}".rstrip("0").rstrip(".")
        return f"{formatted}k"
    return str(stars)


def build_post_caption(item, for_channel: bool = False) -> str:
    """Postarea „sec”: titlu – esență, ce face, ce rezolvă, limbaje, stele,
    link, semnătură. Folosită și pentru cardul din inbox (preview identic)."""
    try:
        meta = json.loads(item["meta"] or "{}")
    except (KeyError, TypeError):
        meta = {}
    title = html.escape(item["title"])
    draft = (item["draft_description"] or (item["summary"] or "")[:400]).strip()
    blocks = [f"<b>{title}</b> – {html.escape(draft)}" if draft else f"<b>{title}</b>"]

    languages = meta.get("languages") or {}
    if languages:
        # jsonb nu păstrează ordinea cheilor — sortăm descrescător la afișare
        ordered = sorted(languages.items(), key=lambda kv: -kv[1])
        blocks.append(
            "Limbaje: "
            + ", ".join(f"{html.escape(str(lang))} ({pct}%)" for lang, pct in ordered)
        )
    stars = meta.get("stars")
    if stars:
        blocks.append(f"⭐️ {_format_stars(int(stars))} stars")

    blocks.append(html.escape(item["url"], quote=True))
    if for_channel and POST_FOOTER:
        blocks.append(html.escape(POST_FOOTER))
    return "\n\n".join(blocks)[:1020]


def _card_caption(item) -> str:
    date = item["published_at"].strftime("%d.%m.%Y") if item["published_at"] else "azi"
    score = f"{item['relevance_score']:.1f}" if item["relevance_score"] is not None else "-"
    caption = (
        build_post_caption(item)
        + "\n\n"
        + texts.INBOX_META_LINE.format(
            source=html.escape(_source_name(item["source"])), date=date, score=score
        )
    )
    return caption[:1020]


def _card_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts.BTN_INBOX_PUBLISH, callback_data=f"inbox_pub:{item_id}"),
                InlineKeyboardButton(text=texts.BTN_INBOX_EDIT, callback_data=f"inbox_edit:{item_id}"),
            ],
            [
                InlineKeyboardButton(text=texts.BTN_INBOX_PHOTO, callback_data=f"inbox_photo:{item_id}"),
                InlineKeyboardButton(text=texts.BTN_INBOX_IGNORE, callback_data=f"inbox_ignore:{item_id}"),
            ],
            [InlineKeyboardButton(text=texts.BTN_INBOX_NEXT, callback_data=f"inbox_next:{item_id}")],
        ]
    )


def _link_preview(item) -> LinkPreviewOptions:
    """Fără imagine proprie, postarea folosește preview-ul mare al linkului,
    afișat deasupra textului — Telegram aduce singur imaginea produsului."""
    return LinkPreviewOptions(
        url=item["url"], prefer_large_media=True, show_above_text=True
    )


async def send_card(bot: Bot, chat_id: int, item) -> None:
    caption = _card_caption(item)
    keyboard = _card_keyboard(item["id"])
    photo = item["photo_file_id"] or item["image_url"]
    if photo:
        try:
            await bot.send_photo(chat_id, photo, caption=caption, reply_markup=keyboard)
            return
        except TelegramBadRequest as exc:
            logger.warning(
                "Imaginea itemului #%d nu a putut fi trimisă (%s) — card cu preview de link.",
                item["id"],
                exc,
            )
    await bot.send_message(
        chat_id, caption, reply_markup=keyboard, link_preview_options=_link_preview(item)
    )


async def _show_next(bot: Bot, chat_id: int, after_id: int) -> None:
    item = await db.next_inbox_item(after_id)
    if item is None:
        await bot.send_message(chat_id, texts.INBOX_EMPTY)
    else:
        await send_card(bot, chat_id, item)


async def _remove_buttons(callback: CallbackQuery) -> None:
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass


# ── Comenzi ──────────────────────────────────────────────────────────────────


@inbox_router.message(Command("pull"))
async def cmd_pull(message: Message) -> None:
    await message.answer(texts.PULL_STARTED)
    report = await scraper.run_pull()
    if report is None:
        await message.answer(texts.PULL_ALREADY_RUNNING)
        return
    per_source = "".join(
        f"  • {html.escape(_source_name(slug))}: {count}\n"
        for slug, count in sorted(report.per_source.items())
    )
    summary = texts.PULL_SUMMARY.format(
        new=report.new,
        filtered=report.filtered,
        duplicates=report.duplicates,
        per_source=per_source,
    )
    for source, error in report.errors.items():
        summary += "\n" + texts.PULL_ERROR_LINE.format(
            source=html.escape(source), error=html.escape(error)
        )
    await message.answer(summary, disable_web_page_preview=True)


@inbox_router.message(Command("inbox"))
async def cmd_inbox(message: Message, bot: Bot) -> None:
    item = await db.next_inbox_item(0)
    if item is None:
        await message.answer(texts.INBOX_EMPTY)
        return
    count = await db.count_inbox_new()
    await message.answer(texts.INBOX_HEADER.format(count=count))
    await send_card(bot, message.chat.id, item)


@inbox_router.message(Command("inboxstats"))
async def cmd_inboxstats(message: Message) -> None:
    rows = await db.inbox_stats()
    if not rows:
        await message.answer(texts.INBOX_STATS_EMPTY)
        return
    per_source: dict[str, dict[str, int]] = {}
    totals: dict[str, int] = {}
    for row in rows:
        per_source.setdefault(row["source"], {})[row["status"]] = row["total"]
        totals[row["status"]] = totals.get(row["status"], 0) + row["total"]
    lines = [texts.INBOX_STATS_HEADER]
    for slug, statuses in sorted(per_source.items()):
        detail = " • ".join(f"{status}: {n}" for status, n in sorted(statuses.items()))
        lines.append(f"<b>{html.escape(_source_name(slug))}</b> — {detail}")
    total_line = " • ".join(f"{status}: {n}" for status, n in sorted(totals.items()))
    lines.append(f"\n<b>Total</b> — {total_line}")
    await message.answer("\n".join(lines))


# ── Butoanele cardului ───────────────────────────────────────────────────────


@inbox_router.callback_query(F.data.startswith("inbox_next:"))
async def inbox_next(callback: CallbackQuery, bot: Bot) -> None:
    current_id = int(callback.data.split(":", 1)[1])
    await callback.answer()
    await _remove_buttons(callback)
    await _show_next(bot, callback.message.chat.id, current_id)


@inbox_router.callback_query(F.data.startswith("inbox_ignore:"))
async def inbox_ignore(callback: CallbackQuery, bot: Bot) -> None:
    item_id = int(callback.data.split(":", 1)[1])
    item = await db.claim_scraped(item_id, "ignored")
    if item is None:
        await callback.answer(texts.INBOX_ALREADY_PROCESSED, show_alert=True)
        return
    logger.info("Item #%d ignorat: %s", item_id, item["title"])
    await callback.answer(texts.INBOX_IGNORED)
    await _remove_buttons(callback)
    await _show_next(bot, callback.message.chat.id, item_id)


@inbox_router.callback_query(F.data.startswith("inbox_pub:"))
async def inbox_publish(callback: CallbackQuery, bot: Bot) -> None:
    item_id = int(callback.data.split(":", 1)[1])
    item = await db.get_scraped(item_id)
    if item is None or item["status"] != "new":
        await callback.answer(texts.INBOX_ALREADY_PROCESSED, show_alert=True)
        return
    photo = item["photo_file_id"] or item["image_url"]
    claimed = await db.claim_scraped(item_id, "published")
    if claimed is None:
        await callback.answer(texts.INBOX_ALREADY_PROCESSED, show_alert=True)
        return

    caption = build_post_caption(item, for_channel=True)
    posted = None
    try:
        if photo:
            try:
                posted = await bot.send_photo(CHANNEL_ID, photo, caption=caption)
            except TelegramBadRequest:
                # imaginea de la sursă nu e acceptată → preview de link
                if item["photo_file_id"]:
                    raise
        if posted is None:
            posted = await bot.send_message(
                CHANNEL_ID, caption, link_preview_options=_link_preview(item)
            )
    except (TelegramForbiddenError, TelegramBadRequest) as exc:
        await db.set_scraped_status(item_id, "new")
        logger.error("Publicarea itemului #%d a eșuat: %s", item_id, exc)
        await callback.answer()
        await callback.message.reply(
            texts.ADMIN_CHANNEL_ERROR.format(error=html.escape(str(exc)))
        )
        return

    await db.set_scraped_status(item_id, "published", posted.message_id)
    logger.info(
        "Item #%d („%s”) publicat în canal (mesajul %d).",
        item_id,
        item["title"],
        posted.message_id,
    )
    url = _post_url(posted.chat, posted.message_id)
    await callback.answer("Publicat ✅")
    await _remove_buttons(callback)
    await callback.message.reply(
        texts.INBOX_PUBLISHED.format(url=url) if url else texts.INBOX_PUBLISHED_NO_LINK
    )
    await _show_next(bot, callback.message.chat.id, item_id)


@inbox_router.callback_query(F.data.startswith("inbox_edit:"))
async def inbox_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":", 1)[1])
    item = await db.get_scraped(item_id)
    if item is None or item["status"] != "new":
        await callback.answer(texts.INBOX_ALREADY_PROCESSED, show_alert=True)
        return
    await state.set_state(InboxEdit.description)
    await state.update_data(item_id=item_id)
    await callback.answer()
    await callback.message.reply(
        texts.INBOX_ASK_DESCRIPTION.format(title=html.escape(item["title"]))
    )


@inbox_router.message(InboxEdit.description, F.text, ~F.text.startswith("/"))
async def inbox_edit_save(message: Message, state: FSMContext, bot: Bot) -> None:
    text = message.text.strip()
    if len(text) > 600:
        await message.answer(texts.INBOX_DESC_TOO_LONG.format(n=len(text)))
        return
    data = await state.get_data()
    await state.clear()
    await db.update_scraped_draft(data["item_id"], text)
    item = await db.get_scraped(data["item_id"])
    await message.answer(texts.INBOX_UPDATED)
    await send_card(bot, message.chat.id, item)


@inbox_router.message(InboxEdit.description, ~F.text.startswith("/"))
async def inbox_edit_wrong(message: Message) -> None:
    await message.answer(texts.ERR_EXPECTED_TEXT)


@inbox_router.callback_query(F.data.startswith("inbox_photo:"))
async def inbox_photo_start(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":", 1)[1])
    item = await db.get_scraped(item_id)
    if item is None or item["status"] != "new":
        await callback.answer(texts.INBOX_ALREADY_PROCESSED, show_alert=True)
        return
    await state.set_state(InboxEdit.photo)
    await state.update_data(item_id=item_id)
    await callback.answer()
    await callback.message.reply(
        texts.INBOX_ASK_PHOTO.format(title=html.escape(item["title"]))
    )


@inbox_router.message(InboxEdit.photo, F.photo)
async def inbox_photo_save(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    await db.update_scraped_photo(data["item_id"], message.photo[-1].file_id)
    item = await db.get_scraped(data["item_id"])
    await message.answer(texts.INBOX_UPDATED)
    await send_card(bot, message.chat.id, item)


@inbox_router.message(InboxEdit.photo, ~F.text.startswith("/"))
async def inbox_photo_wrong(message: Message) -> None:
    await message.answer(texts.INBOX_NOT_A_PHOTO)
