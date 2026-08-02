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
from ..categories import (
    MAX_CATEGORY_NAME_LEN,
    MAX_CUSTOM_CATEGORIES,
    is_default_category,
    normalize_category,
)
from ..keyboards import (
    categories_menu_keyboard,
    settings_currency_keyboard,
    settings_menu_keyboard,
)

S_MENU, S_BASE_OTHER, S_DEFAULT_OTHER, S_CAT_NAME = range(4)

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


# ── Custom categories ────────────────────────────────────────────────────────

async def _render_categories(update: Update, context: ContextTypes.DEFAULT_TYPE,
                             edit: bool, note: str = "") -> int:
    custom = await db.list_custom_categories(context.bot_data["pool"],
                                             update.effective_user.id)
    text = (
        f"🏷 *My categories* — {len(custom)}/{MAX_CUSTOM_CATEGORIES} used.\n"
        "These are added to the built-in ones. Tap 🗑 to remove."
    )
    if note:
        text = f"{note}\n\n{text}"
    markup = categories_menu_keyboard(
        custom, at_limit=len(custom) >= MAX_CUSTOM_CATEGORIES
    )
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=markup
        )
    else:
        await update.effective_message.reply_text(
            text, parse_mode="Markdown", reply_markup=markup
        )
    return S_MENU


async def open_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await _render_categories(update, context, edit=True)


async def prompt_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"Send the new category name (up to {MAX_CATEGORY_NAME_LEN} characters).",
    )
    return S_CAT_NAME


async def receive_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = normalize_category(update.message.text)
    if not name or len(name) > MAX_CATEGORY_NAME_LEN:
        await update.message.reply_text(
            f"Name must be 1–{MAX_CATEGORY_NAME_LEN} characters. Try again."
        )
        return S_CAT_NAME
    if is_default_category(name):
        await update.message.reply_text(
            f"*{name}* already exists as a built-in category.", parse_mode="Markdown"
        )
        return await _render_categories(update, context, edit=False)

    added = await db.add_custom_category(
        context.bot_data["pool"], update.effective_user.id, name,
        MAX_CUSTOM_CATEGORIES,
    )
    note = f"✅ Added *{name}*." if added else f"⚠️ Couldn't add *{name}*."
    return await _render_categories(update, context, edit=False, note=note)


async def delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    name = query.data.split(":", 1)[1]
    await query.answer(f"Removed {name}")
    await db.delete_custom_category(context.bot_data["pool"],
                                    update.effective_user.id, name)
    return await _render_categories(update, context, edit=True,
                                    note=f"🗑 Removed *{name}*.")


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
                CallbackQueryHandler(open_categories,
                                     pattern=r"^settings:categories$"),
                CallbackQueryHandler(prompt_category, pattern=r"^catadd$"),
                CallbackQueryHandler(delete_category, pattern=r"^catdel:"),
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
            S_CAT_NAME: [
                CallbackQueryHandler(open_categories,
                                     pattern=r"^settings:categories$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_category),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
