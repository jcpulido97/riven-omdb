import pytest

from program.metadata import normalize_imdb_id, normalize_item_identifiers


def test_normalize_imdb_id():
    assert normalize_imdb_id("  TT1879016 ") == "tt1879016"
    assert normalize_imdb_id("1879016") is None


def test_numeric_item_id_remains_database_id():
    assert normalize_item_identifiers(42, None) == (42, None)
    assert normalize_item_identifiers("42", None) == (42, None)


def test_imdb_value_in_item_id_is_moved_to_imdb_id():
    assert normalize_item_identifiers("tt1879016", None) == (None, "tt1879016")


def test_matching_explicit_and_item_imdb_ids_are_accepted():
    assert normalize_item_identifiers("TT1879016", "tt1879016") == (
        None,
        "tt1879016",
    )


@pytest.mark.parametrize(
    ("item_id", "imdb_id"),
    [
        ("not-an-id", None),
        (None, "not-an-id"),
        ("tt1879016", "tt3896198"),
    ],
)
def test_invalid_or_conflicting_identifiers_are_rejected(item_id, imdb_id):
    with pytest.raises(ValueError):
        normalize_item_identifiers(item_id, imdb_id)
