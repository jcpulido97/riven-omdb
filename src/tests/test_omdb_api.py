from unittest.mock import Mock

from program.apis.omdb_api import OMDbAPI
from program.metadata import EpisodeMetadata, SeasonMetadata


def test_parse_title_release_date():
    released_at = OMDbAPI.parse_release_date("05 May 2017")

    assert released_at is not None
    assert released_at.isoformat() == "2017-05-05T00:00:00"


def test_parse_season_episode_release_dates():
    season = SeasonMetadata(
        number=2,
        title="Example",
        episodes=[
            EpisodeMetadata(
                number=0,
                title="Pilot",
                released_at=OMDbAPI.parse_release_date("2025-01-01"),
                imdb_id="tt0000000",
            ),
            EpisodeMetadata(
                number=1,
                title="One",
                released_at=OMDbAPI.parse_release_date("2026-08-01"),
                imdb_id="tt0000001",
            ),
            EpisodeMetadata(
                number=2,
                title="Two",
                released_at=OMDbAPI.parse_release_date("N/A"),
                imdb_id="tt0000002",
            ),
        ],
    )

    assert season.released_at is not None
    assert season.released_at.isoformat() == "2026-08-01T00:00:00"
    assert list(season.episode_release_dates()) == [0, 1]


def test_every_request_includes_api_key():
    api = OMDbAPI(api_key="test-key")
    response = Mock()
    response.ok = True
    response.json.return_value = {
        "Title": "Example",
        "Released": "01 Jan 2026",
        "imdbID": "tt0000001",
        "Type": "movie",
        "Response": "True",
    }
    api.session.get = Mock(return_value=response)

    assert api.get_title("tt0000001") is not None
    api.session.get.assert_called_once_with(
        "/",
        params={
            "apikey": "test-key",
            "i": "tt0000001",
            "plot": "short",
            "r": "json",
        },
    )


def test_imdb_id_is_normalized_before_request():
    api = OMDbAPI(api_key="test-key")
    response = Mock()
    response.ok = True
    response.json.return_value = {
        "Title": "Operation Mincemeat",
        "Released": "11 May 2022",
        "imdbID": "tt1879016",
        "Type": "movie",
        "Response": "True",
    }
    api.session.get = Mock(return_value=response)

    title = api.get_title("  TT1879016 ")

    assert title is not None
    assert title.imdb_id == "tt1879016"
    api.session.get.assert_called_once_with(
        "/",
        params={
            "apikey": "test-key",
            "i": "tt1879016",
            "plot": "short",
            "r": "json",
        },
    )


def test_invalid_imdb_id_does_not_make_request():
    api = OMDbAPI(api_key="test-key")
    api.session.get = Mock()

    assert api.get_title("1879016") is None
    api.session.get.assert_not_called()


def test_api_error_returns_none():
    api = OMDbAPI(api_key="test-key")
    response = Mock()
    response.ok = True
    response.json.return_value = {"Response": "False", "Error": "Invalid IMDb ID."}
    api.session.get = Mock(return_value=response)

    assert api.get_title("invalid") is None


def test_missing_api_key_skips_request():
    api = OMDbAPI(api_key="")
    api.api_key = ""
    api.session.get = Mock()

    assert api.get_title("tt0000001") is None
    api.session.get.assert_not_called()
