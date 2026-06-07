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
    "Psychologist",
    "Business",
    "Other",
]

ALL_CATEGORIES = QUICK_CATEGORIES + EXTENDED_CATEGORIES

# Minimum similarity (0-100) to treat a fuzzy place match as the same place.
_FUZZY_CUTOFF = 88


def normalize_place(place: str) -> str:
    return " ".join(place.lower().split())


def suggest_category(
    place_norm: str, known: list[tuple[str, str]]
) -> str | None:
    """Best-effort category for a place given the user's history.

    `known` is a list of (normalized_place, category). Tries exact match first,
    then a conservative fuzzy match.
    """
    if not known:
        return None

    lookup = dict(known)
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
