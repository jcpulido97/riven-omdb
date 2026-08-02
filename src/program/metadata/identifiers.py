import re

IMDB_ID_PATTERN = re.compile(r"^tt\d{7,10}$", re.IGNORECASE)


def normalize_imdb_id(value: str | None) -> str | None:
    if value is None:
        return None

    candidate = value.strip().lower()
    return candidate if IMDB_ID_PATTERN.fullmatch(candidate) else None


def normalize_item_identifiers(
    item_id: str | int | None, imdb_id: str | None
) -> tuple[str | int | None, str | None]:
    normalized_imdb = normalize_imdb_id(imdb_id)
    if imdb_id is not None and normalized_imdb is None:
        raise ValueError("Invalid IMDb ID")

    if isinstance(item_id, str):
        candidate = item_id.strip()
        item_imdb = normalize_imdb_id(candidate)
        if item_imdb:
            if normalized_imdb and normalized_imdb != item_imdb:
                raise ValueError("Conflicting IMDb IDs")
            return None, item_imdb
        if not candidate:
            return None, normalized_imdb
        return candidate, normalized_imdb

    return item_id, normalized_imdb
