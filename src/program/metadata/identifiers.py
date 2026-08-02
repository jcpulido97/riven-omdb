"""Normalization helpers for metadata and database identifiers."""

import re

IMDB_ID_PATTERN = re.compile(r"^tt\d{7,10}$", re.IGNORECASE)


def normalize_imdb_id(value: str | None) -> str | None:
    """Return a canonical IMDb ID or None when the value is invalid."""

    if not value:
        return None

    imdb_id = value.strip().lower()
    return imdb_id if IMDB_ID_PATTERN.fullmatch(imdb_id) else None


def normalize_item_identifiers(
    item_id: int | str | None,
    imdb_id: str | None,
) -> tuple[int | None, str | None]:
    """Split a flexible item identifier into database and IMDb identifiers."""

    normalized_imdb_id = normalize_imdb_id(imdb_id)

    if imdb_id and normalized_imdb_id is None:
        raise ValueError(f"Invalid IMDb ID: {imdb_id!r}")

    if item_id is None:
        return None, normalized_imdb_id

    if isinstance(item_id, int):
        return item_id, normalized_imdb_id

    value = item_id.strip()

    if value.isdigit():
        return int(value), normalized_imdb_id

    item_imdb_id = normalize_imdb_id(value)

    if item_imdb_id is None:
        raise ValueError(f"Invalid item ID: {item_id!r}")

    if normalized_imdb_id and normalized_imdb_id != item_imdb_id:
        raise ValueError("Conflicting IMDb IDs were provided")

    return None, item_imdb_id
