"""Category definitions and place-name normalization / fuzzy matching."""
from __future__ import annotations

from rapidfuzz import fuzz, process

QUICK_CATEGORIES = [
    "Restaurants",
    "Grocery",
    "Housing",
    "Sport",
    "Car",
    "Health & Beauty",
]

EXTENDED_CATEGORIES = [
    "Entertainment",
    "Travel",
    "Taxi & Transport",
    "Clothes",
    "Education",
    "Business",
    "Other",
]

ALL_CATEGORIES = QUICK_CATEGORIES + EXTENDED_CATEGORIES

# Users may add a few categories of their own on top of the defaults above.
MAX_CUSTOM_CATEGORIES = 4

# Keeps `pk:<name>` callback data inside Telegram's 64-byte limit, and the
# button label readable.
MAX_CATEGORY_NAME_LEN = 24


def normalize_category(name: str) -> str:
    return " ".join(name.split())


def is_default_category(name: str) -> bool:
    return name.casefold() in {c.casefold() for c in ALL_CATEGORIES}

# Minimum similarity (0-100) to treat a fuzzy place match as the same place.
_FUZZY_CUTOFF = 88


def normalize_place(place: str) -> str:
    return " ".join(place.lower().split())


def suggest_place(
    place_norm: str, known: list[tuple[str, str, str | None]]
) -> tuple[str, str | None] | None:
    """Best-effort (category, currency) for a place given the user's history.

    `known` is a list of (normalized_place, category, currency). Tries exact
    match first, then a conservative fuzzy match. The currency is None for
    places recorded before the bot started remembering it.
    """
    if not known:
        return None

    lookup = {place: (category, currency) for place, category, currency in known}
    if place_norm in lookup:
        return lookup[place_norm]

    match = process.extractOne(
        place_norm,
        lookup.keys(),
        scorer=fuzz.WRatio,
        score_cutoff=_FUZZY_CUTOFF,
    )
    if match:
        return lookup[match[0]]
    return None
