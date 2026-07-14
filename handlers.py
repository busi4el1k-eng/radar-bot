"""Handlerele botului: formularul fondatorului (FSM) și moderarea adminului."""

import html
import logging
import math
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from dotenv import load_dotenv

import db
import texts

load_dotenv()

logger = logging.getLogger(__name__)

ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}
_raw_channel = os.getenv("CHANNEL_ID", "").strip()
CHANNEL_ID: int | str = (
    int(_raw_channel) if re.fullmatch(r"-?\d+", _raw_channel) else _raw_channel
)

user_router = Router(name="user")
admin_router = Router(name="admin")

# Fluxurile funcționează doar în privat cu botul.
user_router.message.filter(F.chat.type == "private")
admin_router.message.filter(F.chat.type == "private", F.from_user.id.in_(ADMIN_IDS))
admin_router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class SubmissionForm(StatesGroup):
    photo = State()
    name = State()
    description = State()
    link = State()
    contact = State()
    preview = State()


class RejectForm(StatesGroup):
    reason = State()


CONTACT_RE = re.compile(r"^@?[A-Za-z0-9_]{5,32}$")


def normalize_link(raw: str) -> str | None:
    """Validează un URL; acceptă și forma fără schemă (exemplu.ro) → https://."""
    raw = raw.strip()
    if not raw or " " in raw:
        return None
    candidate = raw if raw.lower().startswith(("http://", "https://")) else f"https://{raw}"
    parsed = urlparse(candidate)
    host = parsed.netloc
    if parsed.scheme in ("http", "https") and "." in host and len(host) >= 4:
        return candidate
    return None


def build_post_caption(name: str, description: str, link: str, contact: str) -> str:
    return texts.POST_TEMPLATE.format(
        name=html.escape(name),
        description=html.escape(description),
        link=html.escape(link, quote=True),
        contact=html.escape(contact),
    )


def moderation_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts.BTN_APPROVE, callback_data=f"approve:{sub_id}"),
                InlineKeyboardButton(text=texts.BTN_REJECT, callback_data=f"reject:{sub_id}"),
            ]
        ]
    )


async def send_card_to_admins(bot: Bot, sub) -> None:
    """Trimite fiecărui admin cardul de moderare (poza + caption + butoane)."""
    sender = f"@{sub['username']}" if sub["username"] else f"id {sub['user_id']}"
    caption = texts.ADMIN_NEW_HEADER.format(
        sub_id=sub["id"], sender=html.escape(sender)
    ) + build_post_caption(
        sub["product_name"], sub["description"], sub["link"], sub["contact"]
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                sub["photo_file_id"],
                caption=caption,
                reply_markup=moderation_keyboard(sub["id"]),
            )
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.warning(
                "Nu am putut trimite cardul submisiei #%d adminului %d: %s "
                "(adminul trebuie să pornească o conversație cu botul: /start)",
                sub["id"],
                admin_id,
                exc,
            )


# ── Fluxul fondatorului ──────────────────────────────────────────────────────


@user_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.BTN_ADD, callback_data="new_submission")]
        ]
    )
    await message.answer(texts.WELCOME, reply_markup=keyboard)


@user_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(texts.NOTHING_TO_CANCEL)
        return
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=ReplyKeyboardRemove())


@user_router.callback_query(F.data == "new_submission")
async def start_form(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    last_at = await db.last_recent_submission_at(callback.from_user.id)
    if last_at is not None:
        remaining = last_at + timedelta(days=7) - datetime.now(timezone.utc)
        days = max(1, math.ceil(remaining.total_seconds() / 86400))
        await callback.message.answer(texts.COOLDOWN.format(days=days))
        return
    await state.set_state(SubmissionForm.photo)
    await callback.message.answer(texts.ASK_PHOTO)


@user_router.message(SubmissionForm.photo, F.photo)
async def got_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(SubmissionForm.name)
    await message.answer(texts.ASK_NAME)


@user_router.message(SubmissionForm.photo)
async def wrong_photo(message: Message) -> None:
    await message.answer(texts.ERR_NOT_PHOTO)


@user_router.message(SubmissionForm.name, F.text)
async def got_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) > 50:
        await message.answer(texts.ERR_NAME_TOO_LONG.format(n=len(name)))
        return
    await state.update_data(product_name=name)
    await state.set_state(SubmissionForm.description)
    await message.answer(texts.ASK_DESCRIPTION)


@user_router.message(SubmissionForm.description, F.text)
async def got_description(message: Message, state: FSMContext) -> None:
    description = message.text.strip()
    if len(description) > 300:
        await message.answer(texts.ERR_DESC_TOO_LONG.format(n=len(description)))
        return
    await state.update_data(description=description)
    await state.set_state(SubmissionForm.link)
    await message.answer(texts.ASK_LINK)


@user_router.message(SubmissionForm.link, F.text)
async def got_link(message: Message, state: FSMContext) -> None:
    link = normalize_link(message.text)
    if link is None:
        await message.answer(texts.ERR_BAD_LINK)
        return
    await state.update_data(link=link)
    await state.set_state(SubmissionForm.contact)
    username = message.from_user.username
    if username:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=f"@{username}")]],
            resize_keyboard=True,
            one_time_keyboard=True,
            input_field_placeholder="@username",
        )
        await message.answer(
            texts.ASK_CONTACT_WITH_DEFAULT.format(username=f"@{username}"),
            reply_markup=keyboard,
        )
    else:
        await message.answer(texts.ASK_CONTACT)


@user_router.message(SubmissionForm.contact, F.text)
async def got_contact(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    if not CONTACT_RE.fullmatch(raw):
        await message.answer(texts.ERR_BAD_CONTACT)
        return
    contact = raw if raw.startswith("@") else f"@{raw}"
    await state.update_data(contact=contact)
    await state.set_state(SubmissionForm.preview)
    data = await state.get_data()
    caption = build_post_caption(
        data["product_name"], data["description"], data["link"], data["contact"]
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts.BTN_SUBMIT, callback_data="submit_confirm"),
                InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data="submit_cancel"),
            ]
        ]
    )
    await message.answer(texts.PREVIEW_INTRO, reply_markup=ReplyKeyboardRemove())
    await message.answer_photo(data["photo_file_id"], caption=caption, reply_markup=keyboard)


# Orice altceva decât text la pașii de text (poze, stickere etc.)
@user_router.message(
    StateFilter(
        SubmissionForm.name,
        SubmissionForm.description,
        SubmissionForm.link,
        SubmissionForm.contact,
    )
)
async def expected_text(message: Message) -> None:
    await message.answer(texts.ERR_EXPECTED_TEXT)


@user_router.callback_query(SubmissionForm.preview, F.data == "submit_confirm")
async def submit_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    sub_id = await db.create_submission(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        product_name=data["product_name"],
        description=data["description"],
        link=data["link"],
        contact=data["contact"],
        photo_file_id=data["photo_file_id"],
    )
    logger.info(
        "Submisie nouă #%d: „%s” de la user %d (@%s)",
        sub_id,
        data["product_name"],
        callback.from_user.id,
        callback.from_user.username or "-",
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.answer()
    await callback.message.answer(texts.SUBMITTED)
    sub = await db.get_submission(sub_id)
    await send_card_to_admins(bot, sub)


@user_router.callback_query(SubmissionForm.preview, F.data == "submit_cancel")
async def submit_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.answer()
    await callback.message.answer(texts.CANCELLED)


@user_router.message(StateFilter(None))
async def fallback(message: Message) -> None:
    await message.answer(texts.FALLBACK)


@user_router.callback_query()
async def stale_callback(callback: CallbackQuery) -> None:
    """Butoane vechi/expirate (ex: dublu-click pe Trimite după ce s-a trimis)."""
    await callback.answer(texts.ADMIN_ALREADY_PROCESSED)


# ── Fluxul adminului ─────────────────────────────────────────────────────────


def _post_url(chat, message_id: int) -> str | None:
    if chat.username:
        return f"https://t.me/{chat.username}/{message_id}"
    chat_id = str(chat.id)
    if chat_id.startswith("-100"):
        return f"https://t.me/c/{chat_id[4:]}/{message_id}"
    return None


@admin_router.message(Command("pending"))
async def cmd_pending(message: Message, bot: Bot) -> None:
    pending = await db.get_pending(limit=10)
    if not pending:
        await message.answer(texts.PENDING_EMPTY)
        return
    total = await db.count_pending()
    await message.answer(texts.PENDING_HEADER.format(count=total))
    for sub in pending:
        sender = f"@{sub['username']}" if sub["username"] else f"id {sub['user_id']}"
        caption = texts.ADMIN_NEW_HEADER.format(
            sub_id=sub["id"], sender=html.escape(sender)
        ) + build_post_caption(
            sub["product_name"], sub["description"], sub["link"], sub["contact"]
        )
        await bot.send_photo(
            message.chat.id,
            sub["photo_file_id"],
            caption=caption,
            reply_markup=moderation_keyboard(sub["id"]),
        )


@admin_router.callback_query(F.data.startswith("approve:"))
async def approve_submission(callback: CallbackQuery, bot: Bot) -> None:
    sub_id = int(callback.data.split(":", 1)[1])
    sub = await db.claim(sub_id, "approved")
    if sub is None:
        await callback.answer(texts.ADMIN_ALREADY_PROCESSED, show_alert=True)
        return
    caption = build_post_caption(
        sub["product_name"], sub["description"], sub["link"], sub["contact"]
    )
    try:
        posted = await bot.send_photo(CHANNEL_ID, sub["photo_file_id"], caption=caption)
    except (TelegramForbiddenError, TelegramBadRequest) as exc:
        await db.set_status(sub_id, "pending")
        logger.error("Nu am putut posta în canalul %s: %s", CHANNEL_ID, exc)
        await callback.answer()
        await callback.message.reply(texts.ADMIN_CHANNEL_ERROR.format(error=html.escape(str(exc))))
        return

    logger.info(
        "Submisia #%d („%s”) aprobată și publicată în canal (mesajul %d).",
        sub_id,
        sub["product_name"],
        posted.message_id,
    )
    url = _post_url(posted.chat, posted.message_id)
    try:
        if url:
            await bot.send_message(sub["user_id"], texts.USER_APPROVED.format(url=url))
        else:
            await bot.send_message(sub["user_id"], texts.USER_APPROVED_NO_LINK)
    except TelegramForbiddenError:
        logger.warning(
            "Fondatorul %d a blocat botul — nu am putut trimite anunțul de aprobare.",
            sub["user_id"],
        )
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.answer("Publicat ✅")
    await callback.message.reply(texts.ADMIN_APPROVED_OK.format(sub_id=sub_id))


@admin_router.callback_query(F.data.startswith("reject:"))
async def reject_start(callback: CallbackQuery, state: FSMContext) -> None:
    sub_id = int(callback.data.split(":", 1)[1])
    sub = await db.get_submission(sub_id)
    if sub is None or sub["status"] != "pending":
        await callback.answer(texts.ADMIN_ALREADY_PROCESSED, show_alert=True)
        return
    await state.set_state(RejectForm.reason)
    await state.update_data(
        sub_id=sub_id,
        card_chat_id=callback.message.chat.id,
        card_message_id=callback.message.message_id,
    )
    await callback.answer()
    await callback.message.reply(
        texts.ADMIN_ASK_REASON.format(name=html.escape(sub["product_name"]))
    )


@admin_router.message(RejectForm.reason, F.text, ~F.text.startswith("/"))
async def reject_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    sub = await db.claim(data["sub_id"], "rejected")
    if sub is None:
        await message.answer(texts.ADMIN_ALREADY_PROCESSED)
        return
    reason = message.text.strip()
    logger.info("Submisia #%d („%s”) respinsă. Motiv: %s", sub["id"], sub["product_name"], reason)
    try:
        await bot.send_message(
            sub["user_id"], texts.USER_REJECTED.format(reason=html.escape(reason))
        )
    except TelegramForbiddenError:
        logger.warning(
            "Fondatorul %d a blocat botul — nu am putut trimite motivul respingerii.",
            sub["user_id"],
        )
    try:
        await bot.edit_message_reply_markup(
            chat_id=data["card_chat_id"],
            message_id=data["card_message_id"],
            reply_markup=None,
        )
    except TelegramBadRequest:
        pass
    await message.answer(texts.ADMIN_REJECTED_OK)


@admin_router.my_chat_member()
async def bot_membership_changed(event: ChatMemberUpdated, bot: Bot) -> None:
    """Alertează adminii dacă botul își pierde drepturile în canal."""
    chat = event.chat
    if chat.type != "channel":
        return
    if isinstance(CHANNEL_ID, int):
        if chat.id != CHANNEL_ID:
            return
    elif not (chat.username and f"@{chat.username}".lower() == str(CHANNEL_ID).lower()):
        return
    if event.new_chat_member.status in ("left", "kicked", "member", "restricted"):
        logger.error(
            "Botul nu mai are drepturi de administrator în canalul %s (status: %s).",
            CHANNEL_ID,
            event.new_chat_member.status,
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, texts.ADMIN_BOT_REMOVED)
            except (TelegramForbiddenError, TelegramBadRequest):
                pass
