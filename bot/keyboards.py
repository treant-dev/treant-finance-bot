"""Inline keyboard builders."""
from __future__ import annotations

import datetime as dt

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .categories import EXTENDED_CATEGORIES, QUICK_CATEGORIES

# Currencies offered on expense entry (default marked with a dot).
EXPENSE_CURRENCIES = ["RSD", "EUR", "USD", "RUB"]
DEFAULT_CURRENCY = "RSD"

# Base-currency options during onboarding.
BASE_CURRENCIES = ["EUR", "USD", "RSD"]


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _date_label(d: dt.date) -> str:
    today = dt.date.today()
    if d == today:
        return "Today"
    if d == today - dt.timedelta(days=1):
        return "Yesterday"
    return d.isoformat()


# ── Onboarding ───────────────────────────────────────────────────────────────

def base_currency_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(c, callback_data=f"base:{c}") for c in BASE_CURRENCIES]
    row.append(InlineKeyboardButton("Other", callback_data="base:OTHER"))
    return InlineKeyboardMarkup([row])


def default_currency_keyboard() -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(c, callback_data=f"default:{c}")
        for c in EXPENSE_CURRENCIES
    ]
    row.append(InlineKeyboardButton("Other", callback_data="default:OTHER"))
    return InlineKeyboardMarkup([row])


# ── Expense card ─────────────────────────────────────────────────────────────

def expense_card_keyboard(draft: dict, default_currency: str) -> InlineKeyboardMarkup:
    cur = draft["currency"]
    cur_label = f"{cur} (default)" if cur == default_currency else cur
    category = draft["category"] or "❓ choose"
    comment = draft["comment"] or "—"
    rows = [
        [InlineKeyboardButton(f"💰 Amount: {draft['amount']:g}", callback_data="f:amount")],
        [InlineKeyboardButton(f"📍 Place: {draft['place']}", callback_data="f:place")],
        [InlineKeyboardButton(f"💱 Currency: {cur_label}", callback_data="f:currency")],
        [InlineKeyboardButton(f"🏷 Category: {category}", callback_data="f:category")],
        [InlineKeyboardButton(f"💬 Comment: {comment}", callback_data="f:comment")],
        [InlineKeyboardButton(f"📅 Date: {_date_label(draft['date'])}", callback_data="f:date")],
        [
            InlineKeyboardButton("💾 Save", callback_data="save"),
            InlineKeyboardButton("✖ Cancel", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def card_currency_picker(current: str) -> InlineKeyboardMarkup:
    currencies = list(EXPENSE_CURRENCIES)
    if current not in currencies:
        currencies.insert(0, current)
    buttons = [
        InlineKeyboardButton(f"• {c}" if c == current else c, callback_data=f"pc:{c}")
        for c in currencies
    ]
    rows = _chunk(buttons, 4)
    rows.append([InlineKeyboardButton("Other…", callback_data="pc:OTHER")])
    rows.append([InlineKeyboardButton("« Back", callback_data="card")])
    return InlineKeyboardMarkup(rows)


def card_category_picker(
    suggested: str | None = None, expanded: bool = False
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if suggested:
        rows.append(
            [InlineKeyboardButton(f"✓ {suggested}", callback_data=f"pk:{suggested}")]
        )
    quick = [InlineKeyboardButton(c, callback_data=f"pk:{c}") for c in QUICK_CATEGORIES]
    rows.extend(_chunk(quick, 2))
    if expanded:
        ext = [InlineKeyboardButton(c, callback_data=f"pk:{c}") for c in EXTENDED_CATEGORIES]
        rows.extend(_chunk(ext, 2))
    else:
        rows.append([InlineKeyboardButton("More…", callback_data="pk:__more__")])
    rows.append([InlineKeyboardButton("« Back", callback_data="card")])
    return InlineKeyboardMarkup(rows)


def card_date_picker() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Today", callback_data="pd:today"),
                InlineKeyboardButton("Yesterday", callback_data="pd:yesterday"),
            ],
            [InlineKeyboardButton("Pick date…", callback_data="pd:pick")],
            [InlineKeyboardButton("« Back", callback_data="card")],
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="card")]])


# ── Settings ─────────────────────────────────────────────────────────────────

def settings_menu_keyboard(base: str, default: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"💱 Base currency: {base}",
                                  callback_data="settings:base")],
            [InlineKeyboardButton(f"🪙 Default input: {default}",
                                  callback_data="settings:default")],
            [InlineKeyboardButton("📄 Connected sheet",
                                  callback_data="settings:sheet")],
            [InlineKeyboardButton("🏁 Close", callback_data="settings:close")],
        ]
    )


def settings_currency_keyboard(prefix: str, current: str) -> InlineKeyboardMarkup:
    """Currency picker for settings; `prefix` is e.g. 'setbase' or 'setdef'."""
    buttons = [
        InlineKeyboardButton(f"• {c}" if c == current else c,
                             callback_data=f"{prefix}:{c}")
        for c in EXPENSE_CURRENCIES
    ]
    rows = _chunk(buttons, 4)
    rows.append([InlineKeyboardButton("Other…", callback_data=f"{prefix}:OTHER")])
    rows.append([InlineKeyboardButton("« Back", callback_data="settings:menu")])
    return InlineKeyboardMarkup(rows)
