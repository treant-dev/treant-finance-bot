"""Expense entry conversation: amount+place -> currency -> category -> comment -> date."""
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

from .. import db
from ..categories import normalize_place, suggest_category
from ..keyboards import (
    category_keyboard,
    comment_keyboard,
    currency_keyboard,
    date_keyboard,
)

logger = logging.getLogger(__name__)

(CHOOSE_CURRENCY, CURRENCY_OTHER, CHOOSE_CATEGORY, ASK_COMMENT, ASK_DATE,
 PICK_DATE) = range(6)

ENTRY_RE = re.compile(r"^\s*(\d+(?:[.,]\d{1,2})?)\s+(.+)$")
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pool = context.bot_data["pool"]
    user = await db.get_user(pool, update.effective_user.id)
    if not user:
        await update.message.reply_text("Please send /start first to set things up.")
        return ConversationHandler.END

    match = ENTRY_RE.match(update.message.text)
    if not match:  # Shouldn't happen given the entry filter, but be safe.
        return ConversationHandler.END

    amount = float(match.group(1).replace(",", "."))
    place = match.group(2).strip()
    context.user_data["expense"] = {"amount": amount, "place": place}

    await update.message.reply_text(
        f"💸 *{amount:g}* at *{place}* — which currency?",
        parse_mode="Markdown",
        reply_markup=currency_keyboard(default=user["default_currency"]),
    )
    return CHOOSE_CURRENCY


async def choose_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]
    if code == "OTHER":
        await query.edit_message_text("Send the 3-letter currency code (e.g. `GBP`).",
                                      parse_mode="Markdown")
        return CURRENCY_OTHER
    context.user_data["expense"]["currency"] = code
    return await _ask_category(update, context, edit=True)


async def receive_currency_other(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    code = update.message.text.strip().upper()
    if not _CURRENCY_RE.match(code):
        await update.message.reply_text("Please send a 3-letter code, e.g. `GBP`.",
                                        parse_mode="Markdown")
        return CURRENCY_OTHER
    context.user_data["expense"]["currency"] = code
    return await _ask_category(update, context, edit=False)


async def _ask_category(
    update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool
) -> int:
    pool = context.bot_data["pool"]
    place_norm = normalize_place(context.user_data["expense"]["place"])
    known = await db.list_place_categories(pool, update.effective_user.id)
    suggested = suggest_category(place_norm, known)
    context.user_data["expense"]["suggested"] = suggested

    text = "Pick a category:"
    markup = category_keyboard(suggested=suggested)
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)
    return CHOOSE_CATEGORY


async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    value = query.data.split(":", 1)[1]

    if value == "__more__":
        suggested = context.user_data["expense"].get("suggested")
        await query.edit_message_reply_markup(
            reply_markup=category_keyboard(suggested=suggested, expanded=True)
        )
        return CHOOSE_CATEGORY

    context.user_data["expense"]["category"] = value
    await query.edit_message_text(
        f"Category: *{value}*. Add a comment, or skip.",
        parse_mode="Markdown",
        reply_markup=comment_keyboard(),
    )
    return ASK_COMMENT


async def skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["expense"]["comment"] = ""
    await query.edit_message_text("When was it?", reply_markup=date_keyboard())
    return ASK_DATE


async def receive_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["expense"]["comment"] = update.message.text.strip()
    await update.message.reply_text("When was it?", reply_markup=date_keyboard())
    return ASK_DATE


async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    today = dt.date.today()

    if choice == "today":
        return await _finalize(update, context, today, edit=True)
    if choice == "yesterday":
        return await _finalize(update, context, today - dt.timedelta(days=1), edit=True)

    await query.edit_message_text("Send the date as `YYYY-MM-DD`.", parse_mode="Markdown")
    return PICK_DATE


async def receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not _DATE_RE.match(text):
        await update.message.reply_text("Please use the format `YYYY-MM-DD`.",
                                        parse_mode="Markdown")
        return PICK_DATE
    try:
        date = dt.date.fromisoformat(text)
    except ValueError:
        await update.message.reply_text("That's not a valid date. Try `YYYY-MM-DD`.",
                                        parse_mode="Markdown")
        return PICK_DATE
    return await _finalize(update, context, date, edit=False)


async def _finalize(
    update: Update, context: ContextTypes.DEFAULT_TYPE, expense_date: dt.date, edit: bool
) -> int:
    pool = context.bot_data["pool"]
    rates = context.bot_data["rates"]
    sheets = context.bot_data["sheets"]
    tg_id = update.effective_user.id

    user = await db.get_user(pool, tg_id)
    exp = context.user_data["expense"]
    base_currency = user["base_currency"]

    amount_base = await rates.convert(exp["amount"], exp["currency"], base_currency)

    recorded_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [
        recorded_at,
        expense_date.isoformat(),
        exp["amount"],
        exp["currency"],
        "" if amount_base is None else amount_base,
        base_currency,
        exp["category"],
        exp["place"],
        exp.get("comment", ""),
    ]

    try:
        await sheets.append_expense(user["sheet_id"], row)
    except Exception:
        logger.exception("Failed to append row for user %s", tg_id)
        await _reply(update, edit,
                     "⚠️ Couldn't write to your sheet. Is it still shared with me?")
        context.user_data.clear()
        return ConversationHandler.END

    # Learn the place -> category mapping for next time.
    await db.upsert_place_category(
        pool, tg_id, normalize_place(exp["place"]), exp["category"]
    )

    if amount_base is None:
        converted = f"(couldn't convert {exp['currency']}→{base_currency})"
    else:
        converted = f"≈ {amount_base:g} {base_currency}"
    summary = (
        f"✅ Saved: *{exp['amount']:g} {exp['currency']}* {converted}\n"
        f"{exp['category']} · {exp['place']} · {expense_date.isoformat()}"
    )
    await _reply(update, edit, summary)
    context.user_data.clear()
    return ConversationHandler.END


async def _reply(update: Update, edit: bool, text: str) -> None:
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(text, parse_mode="Markdown")


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
            CHOOSE_CURRENCY: [CallbackQueryHandler(choose_currency, pattern=r"^cur:")],
            CURRENCY_OTHER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_currency_other)
            ],
            CHOOSE_CATEGORY: [CallbackQueryHandler(choose_category, pattern=r"^cat:")],
            ASK_COMMENT: [
                CallbackQueryHandler(skip_comment, pattern=r"^comment:skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_comment),
            ],
            ASK_DATE: [CallbackQueryHandler(choose_date, pattern=r"^date:")],
            PICK_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_date)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
