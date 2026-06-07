"""/settings menu: view and change base currency, default currency, sheet."""
from __future__ import annotations

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .. import db
from ..keyboards import settings_currency_keyboard, settings_menu_keyboard

S_MENU, S_BASE_OTHER, S_DEFAULT_OTHER = range(3)

_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
_MENU_TEXT = "⚙️ *Settings* — tap a setting to change it."


async def _render_menu(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       edit: bool) -> int:
    user = await db.get_user(context.bot_data["pool"], update.effective_user.id)
    markup = settings_menu_keyboard(user["base_currency"], user["default_currency"])
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            _MENU_TEXT, parse_mode="Markdown", reply_markup=markup
        )
    else:
        await update.effective_message.reply_text(
            _MENU_TEXT, parse_mode="Markdown", reply_markup=markup
        )
    return S_MENU


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await db.get_user(context.bot_data["pool"], update.effective_user.id)
    if not user:
        await update.message.reply_text("Please send /start first to set things up.")
        return ConversationHandler.END
    return await _render_menu(update, context, edit=False)


async def open_base(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = await db.get_user(context.bot_data["pool"], update.effective_user.id)
    await query.edit_message_text(
        "Choose your *base* (conversion) currency:",
        parse_mode="Markdown",
        reply_markup=settings_currency_keyboard("setbase", user["base_currency"]),
    )
    return S_MENU


async def open_default(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = await db.get_user(context.bot_data["pool"], update.effective_user.id)
    await query.edit_message_text(
        "Choose your *default* input currency:",
        parse_mode="Markdown",
        reply_markup=settings_currency_keyboard("setdef", user["default_currency"]),
    )
    return S_MENU


async def set_base(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    code = query.data.split(":", 1)[1]
    if code == "OTHER":
        await query.answer()
        await query.edit_message_text("Send a 3-letter currency code (e.g. `GBP`).",
                                      parse_mode="Markdown")
        return S_BASE_OTHER
    await query.answer(f"Base currency: {code}")
    await db.update_base_currency(context.bot_data["pool"],
                                  update.effective_user.id, code)
    return await _render_menu(update, context, edit=True)


async def set_default(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    code = query.data.split(":", 1)[1]
    if code == "OTHER":
        await query.answer()
        await query.edit_message_text("Send a 3-letter currency code (e.g. `GBP`).",
                                      parse_mode="Markdown")
        return S_DEFAULT_OTHER
    await query.answer(f"Default input: {code}")
    await db.update_default_currency(context.bot_data["pool"],
                                     update.effective_user.id, code)
    return await _render_menu(update, context, edit=True)


async def receive_base_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip().upper()
    if not _CURRENCY_RE.match(code):
        await update.message.reply_text("Please send a 3-letter code, e.g. `GBP`.",
                                        parse_mode="Markdown")
        return S_BASE_OTHER
    await db.update_base_currency(context.bot_data["pool"],
                                  update.effective_user.id, code)
    return await _render_menu(update, context, edit=False)


async def receive_default_other(update: Update,
                                context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip().upper()
    if not _CURRENCY_RE.match(code):
        await update.message.reply_text("Please send a 3-letter code, e.g. `GBP`.",
                                        parse_mode="Markdown")
        return S_DEFAULT_OTHER
    await db.update_default_currency(context.bot_data["pool"],
                                     update.effective_user.id, code)
    return await _render_menu(update, context, edit=False)


async def show_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = await db.get_user(context.bot_data["pool"], update.effective_user.id)
    url = f"https://docs.google.com/spreadsheets/d/{user['sheet_id']}"
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📄 Open sheet", url=url)],
            [InlineKeyboardButton("« Back", callback_data="settings:menu")],
        ]
    )
    await query.edit_message_text(
        "Your connected sheet (to reconnect a different one, run /start):",
        reply_markup=markup,
    )
    return S_MENU


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await _render_menu(update, context, edit=True)


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Settings closed. Send /settings anytime.")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Closed settings.")
    return ConversationHandler.END


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("settings", settings_cmd)],
        states={
            S_MENU: [
                CallbackQueryHandler(open_base, pattern=r"^settings:base$"),
                CallbackQueryHandler(open_default, pattern=r"^settings:default$"),
                CallbackQueryHandler(show_sheet, pattern=r"^settings:sheet$"),
                CallbackQueryHandler(back_to_menu, pattern=r"^settings:menu$"),
                CallbackQueryHandler(close, pattern=r"^settings:close$"),
                CallbackQueryHandler(set_base, pattern=r"^setbase:"),
                CallbackQueryHandler(set_default, pattern=r"^setdef:"),
            ],
            S_BASE_OTHER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_base_other)
            ],
            S_DEFAULT_OTHER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_default_other)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
