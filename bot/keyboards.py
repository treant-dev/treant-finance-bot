"""Inline keyboard builders."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .categories import EXTENDED_CATEGORIES, QUICK_CATEGORIES

# Currencies offered on expense entry (default marked with a dot).
EXPENSE_CURRENCIES = ["RSD", "EUR", "USD", "RUB"]
DEFAULT_CURRENCY = "RSD"

# Base-currency options during onboarding.
BASE_CURRENCIES = ["EUR", "USD", "RSD"]


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


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


def currency_keyboard(default: str = DEFAULT_CURRENCY) -> InlineKeyboardMarkup:
    # Always include the user's default, even if it isn't a standard option.
    currencies = list(EXPENSE_CURRENCIES)
    if default not in currencies:
        currencies.insert(0, default)
    buttons = []
    for c in currencies:
        label = f"• {c}" if c == default else c
        buttons.append(InlineKeyboardButton(label, callback_data=f"cur:{c}"))
    rows = _chunk(buttons, 4)
    rows.append([InlineKeyboardButton("Other…", callback_data="cur:OTHER")])
    return InlineKeyboardMarkup(rows)


def category_keyboard(
    suggested: str | None = None, expanded: bool = False
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if suggested:
        rows.append(
            [InlineKeyboardButton(f"✓ {suggested}", callback_data=f"cat:{suggested}")]
        )

    quick = [InlineKeyboardButton(c, callback_data=f"cat:{c}") for c in QUICK_CATEGORIES]
    rows.extend(_chunk(quick, 2))

    if expanded:
        ext = [
            InlineKeyboardButton(c, callback_data=f"cat:{c}")
            for c in EXTENDED_CATEGORIES
        ]
        rows.extend(_chunk(ext, 2))
    else:
        rows.append([InlineKeyboardButton("More…", callback_data="cat:__more__")])

    return InlineKeyboardMarkup(rows)


def comment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Skip", callback_data="comment:skip")]]
    )


def date_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Today", callback_data="date:today"),
                InlineKeyboardButton("Yesterday", callback_data="date:yesterday"),
            ],
            [InlineKeyboardButton("Pick date…", callback_data="date:pick")],
        ]
    )
