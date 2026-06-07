"""Expense entry as a single editable card: prefill everything, tap to change, Save."""
from __future__ import annotations

import datetime as dt
import logging
import re

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .. import clock, db
from ..categories import normalize_place, suggest_category
from ..keyboards import (
    back_keyboard,
    card_category_picker,
    card_currency_picker,
    card_date_picker,
    expense_card_keyboard,
)

logger = logging.getLogger(__name__)

CARD, AWAIT_TEXT = range(2)

ENTRY_RE = re.compile(r"^\s*(\d+(?:[.,]\d{1,2})?)\s+(.+)$")
_AMOUNT_RE = re.compile(r"^\d+(?:[.,]\d{1,2})?$")
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_CARD_TEXT = "📝 *New expense* — tap a field to edit, then *Save*."
_CARD_TEXT_NO_CATEGORY = _CARD_TEXT + "\n\n⚠️ Pick a category first."


# ── Card rendering ───────────────────────────────────────────────────────────

async def _set_card_message(context, text, markup) -> None:
    await context.bot.edit_message_text(
        chat_id=context.user_data["card_chat"],
        message_id=context.user_data["card_msg"],
        text=text,
        parse_mode="Markdown",
        reply_markup=markup,
    )


async def _show_card(context, missing_category: bool = False) -> int:
    draft = context.user_data["draft"]
    default = context.user_data["default_currency"]
    text = _CARD_TEXT_NO_CATEGORY if missing_category else _CARD_TEXT
    await _set_card_message(context, text, expense_card_keyboard(draft, default))
    return CARD


async def _prompt_text(context, field: str, prompt: str) -> int:
    context.user_data["editing"] = field
    await _set_card_message(context, prompt, back_keyboard())
    return AWAIT_TEXT


# ── Entry ────────────────────────────────────────────────────────────────────

async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pool = context.bot_data["pool"]
    user = await db.get_user(pool, update.effective_user.id)
    if not user:
        await update.message.reply_text("Please send /start first to set things up.")
        return ConversationHandler.END

    match = ENTRY_RE.match(update.message.text)
    if not match:
        return ConversationHandler.END

    place = match.group(2).strip()
    known = await db.list_place_categories(pool, update.effective_user.id)
    suggested = suggest_category(normalize_place(place), known)

    context.user_data["default_currency"] = user["default_currency"]
    context.user_data["draft"] = {
        "amount": float(match.group(1).replace(",", ".")),
        "place": place,
        "currency": user["default_currency"],
        "category": suggested,
        "comment": "",
        "date": clock.today(),
    }

    sent = await update.message.reply_text(
        _CARD_TEXT,
        parse_mode="Markdown",
        reply_markup=expense_card_keyboard(
            context.user_data["draft"], user["default_currency"]
        ),
    )
    context.user_data["card_chat"] = sent.chat_id
    context.user_data["card_msg"] = sent.message_id
    return CARD


# ── Field taps (CARD state) ──────────────────────────────────────────────────

async def tap_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    field = query.data.split(":", 1)[1]
    draft = context.user_data["draft"]

    if field == "amount":
        return await _prompt_text(context, "amount", "💰 Send the new amount:")
    if field == "place":
        return await _prompt_text(context, "place", "📍 Send the new place:")
    if field == "comment":
        return await _prompt_text(context, "comment", "💬 Send a comment:")
    if field == "currency":
        await _set_card_message(context, "Select currency:",
                                card_currency_picker(draft["currency"]))
        return CARD
    if field == "category":
        await _set_card_message(context, "Select category:",
                                card_category_picker(draft["category"]))
        return CARD
    if field == "date":
        await _set_card_message(context, "Select date:", card_date_picker())
        return CARD
    return CARD


async def pick_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]
    if code == "OTHER":
        return await _prompt_text(context, "currency",
                                  "💱 Send a 3-letter currency code (e.g. `GBP`):")
    context.user_data["draft"]["currency"] = code
    return await _show_card(context)


async def pick_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    value = query.data.split(":", 1)[1]
    if value == "__more__":
        await query.edit_message_reply_markup(
            reply_markup=card_category_picker(
                context.user_data["draft"]["category"], expanded=True
            )
        )
        return CARD
    context.user_data["draft"]["category"] = value
    return await _show_card(context)


async def pick_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    today = clock.today()
    if choice == "today":
        context.user_data["draft"]["date"] = today
    elif choice == "yesterday":
        context.user_data["draft"]["date"] = today - dt.timedelta(days=1)
    elif choice == "pick":
        return await _prompt_text(context, "date", "📅 Send the date as `YYYY-MM-DD`:")
    return await _show_card(context)


async def back_to_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    context.user_data.pop("editing", None)
    return await _show_card(context)


# ── Typed edits (AWAIT_TEXT state) ───────────────────────────────────────────

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.get("editing")
    text = update.message.text.strip()
    draft = context.user_data["draft"]

    if field == "amount":
        if not _AMOUNT_RE.match(text):
            await update.message.reply_text("Please send a number, e.g. `2500`.",
                                            parse_mode="Markdown")
            return AWAIT_TEXT
        draft["amount"] = float(text.replace(",", "."))
    elif field == "place":
        draft["place"] = text
    elif field == "comment":
        draft["comment"] = text
    elif field == "currency":
        if not _CURRENCY_RE.match(text):
            await update.message.reply_text("Please send a 3-letter code, e.g. `GBP`.",
                                            parse_mode="Markdown")
            return AWAIT_TEXT
        draft["currency"] = text.upper()
    elif field == "date":
        if not _DATE_RE.match(text):
            await update.message.reply_text("Please use `YYYY-MM-DD`.",
                                            parse_mode="Markdown")
            return AWAIT_TEXT
        try:
            draft["date"] = dt.date.fromisoformat(text)
        except ValueError:
            await update.message.reply_text("That's not a valid date. Try `YYYY-MM-DD`.",
                                            parse_mode="Markdown")
            return AWAIT_TEXT

    context.user_data.pop("editing", None)
    return await _show_card(context)


# ── Save / cancel ────────────────────────────────────────────────────────────

async def save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    draft = context.user_data["draft"]

    if not draft["category"]:
        await query.answer("Pick a category first", show_alert=False)
        return await _show_card(context, missing_category=True)

    await query.answer("Saving…")
    pool = context.bot_data["pool"]
    rates = context.bot_data["rates"]
    sheets = context.bot_data["sheets"]
    tg_id = update.effective_user.id
    user = await db.get_user(pool, tg_id)
    base_currency = user["base_currency"]

    amount_base = await rates.convert(draft["amount"], draft["currency"], base_currency)

    row = [
        clock.now().strftime("%Y-%m-%d %H:%M:%S"),
        draft["date"].isoformat(),
        draft["amount"],
        draft["currency"],
        "" if amount_base is None else amount_base,
        base_currency,
        draft["category"],
        draft["place"],
        draft["comment"],
    ]

    try:
        await sheets.append_expense(user["sheet_id"], row)
    except Exception:
        logger.exception("Failed to append row for user %s", tg_id)
        await _set_card_message(
            context, "⚠️ Couldn't write to your sheet. Is it still shared with me?", None
        )
        context.user_data.clear()
        return ConversationHandler.END

    await db.upsert_place_category(
        pool, tg_id, normalize_place(draft["place"]), draft["category"]
    )

    if amount_base is None:
        converted = f"(couldn't convert {draft['currency']}→{base_currency})"
    else:
        converted = f"≈ {amount_base:g} {base_currency}"
    summary = (
        f"✅ Saved: *{draft['amount']:g} {draft['currency']}* {converted}\n"
        f"{draft['category']} · {draft['place']} · {draft['date'].isoformat()}"
    )
    await _set_card_message(context, summary, None)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await _set_card_message(context, "✖ Cancelled.", None)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(ENTRY_RE) & ~filters.COMMAND, entry)
        ],
        states={
            CARD: [
                CallbackQueryHandler(tap_field, pattern=r"^f:"),
                CallbackQueryHandler(pick_currency, pattern=r"^pc:"),
                CallbackQueryHandler(pick_category, pattern=r"^pk:"),
                CallbackQueryHandler(pick_date, pattern=r"^pd:"),
                CallbackQueryHandler(back_to_card, pattern=r"^card$"),
                CallbackQueryHandler(save, pattern=r"^save$"),
                CallbackQueryHandler(cancel_button, pattern=r"^cancel$"),
            ],
            AWAIT_TEXT: [
                CallbackQueryHandler(back_to_card, pattern=r"^card$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
