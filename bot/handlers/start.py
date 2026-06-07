"""Onboarding conversation: connect a sheet and pick a base currency."""
from __future__ import annotations

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from .. import db
from ..keyboards import base_currency_keyboard, default_currency_keyboard

(ASK_SHEET, ASK_BASE, ASK_BASE_OTHER, ASK_DEFAULT, ASK_DEFAULT_OTHER) = range(5)

_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")


def _template_link(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.bot_data["config"].template_sheet_url


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pool = context.bot_data["pool"]
    user = await db.get_user(pool, update.effective_user.id)
    if user:
        await update.message.reply_text(
            "You're all set! Just send me an expense like:\n\n"
            "`23000 Ikea`\n\nand I'll log it to your sheet.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    sheets = context.bot_data["sheets"]
    template = _template_link(context)

    if template:
        # URL goes in a button, not inline text — Markdown would mangle the
        # underscores in the sheet ID.
        step1 = "1. Open the template below and make a copy.\n\n"
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📄 Open template", url=template)]]
        )
    else:
        step1 = "1. Create a Google Sheet with the expected columns.\n\n"
        markup = None

    await update.message.reply_text(
        "👋 Welcome to *Treant Finance*!\n\n"
        "Let's connect your Google Sheet:\n\n"
        f"{step1}"
        "2. Click *Share* and add this address as *Editor*:\n"
        f"`{sheets.client_email}`\n\n"
        "3. Paste the link to your sheet here.",
        parse_mode="Markdown",
        reply_markup=markup,
    )
    return ASK_SHEET


async def receive_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sheets = context.bot_data["sheets"]
    sheet_id = sheets.extract_sheet_id(update.message.text)
    if not sheet_id:
        await update.message.reply_text(
            "That doesn't look like a Google Sheets link. Please paste the full URL."
        )
        return ASK_SHEET

    if not await sheets.verify_access(sheet_id):
        await update.message.reply_text(
            "I can't access that sheet yet. Make sure you shared it as *Editor* with:\n"
            f"`{sheets.client_email}`\n\nThen paste the link again.",
            parse_mode="Markdown",
        )
        return ASK_SHEET

    context.user_data["sheet_id"] = sheet_id
    await update.message.reply_text(
        "✅ Connected! Which currency should I convert everything to (your base)?",
        reply_markup=base_currency_keyboard(),
    )
    return ASK_BASE


async def choose_base(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]

    if choice == "OTHER":
        await query.edit_message_text("Send me your base currency code (e.g. `GBP`).",
                                      parse_mode="Markdown")
        return ASK_BASE_OTHER

    context.user_data["base_currency"] = choice
    return await _prompt_default(update, context, edit=True)


async def receive_base_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip().upper()
    if not _CURRENCY_RE.match(code):
        await update.message.reply_text("Please send a 3-letter currency code, e.g. `GBP`.",
                                        parse_mode="Markdown")
        return ASK_BASE_OTHER
    context.user_data["base_currency"] = code
    return await _prompt_default(update, context, edit=False)


async def _prompt_default(
    update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool
) -> int:
    text = (
        "Which currency do you usually pay in? "
        "I'll pre-select it for every new expense (you can always change it)."
    )
    markup = default_currency_keyboard()
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)
    return ASK_DEFAULT


async def choose_default(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]

    if choice == "OTHER":
        await query.edit_message_text("Send your default currency code (e.g. `GBP`).",
                                      parse_mode="Markdown")
        return ASK_DEFAULT_OTHER

    return await _finish(update, context, choice, edit=True)


async def receive_default_other(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    code = update.message.text.strip().upper()
    if not _CURRENCY_RE.match(code):
        await update.message.reply_text("Please send a 3-letter currency code, e.g. `GBP`.",
                                        parse_mode="Markdown")
        return ASK_DEFAULT_OTHER
    return await _finish(update, context, code, edit=False)


async def _finish(
    update: Update, context: ContextTypes.DEFAULT_TYPE, default_currency: str, edit: bool
) -> int:
    pool = context.bot_data["pool"]
    sheet_id = context.user_data["sheet_id"]
    base_currency = context.user_data["base_currency"]
    await db.create_user(
        pool, update.effective_user.id, sheet_id, base_currency, default_currency
    )
    context.user_data.clear()

    text = (
        f"🎉 All set!\nBase currency: *{base_currency}* · "
        f"Default input: *{default_currency}*.\n\n"
        "To log an expense, just send *amount + place*, e.g.:\n"
        "`23000 Ikea`\n\n"
        "I'll ask for currency, category, an optional comment and date — then save it."
    )
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Onboarding cancelled. Send /start to try again.")
    return ConversationHandler.END


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_SHEET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sheet)
            ],
            ASK_BASE: [CallbackQueryHandler(choose_base, pattern=r"^base:")],
            ASK_BASE_OTHER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_base_other)
            ],
            ASK_DEFAULT: [CallbackQueryHandler(choose_default, pattern=r"^default:")],
            ASK_DEFAULT_OTHER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_default_other)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
