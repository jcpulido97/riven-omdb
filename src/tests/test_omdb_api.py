from unittest.mock import Mock

from program.apis.omdb_api import OMDbAPI, OMDbSeason, OMDbTitle


def test_parse_title_release_date():
    title = OMDbTitle.model_validate(
        {
            "Title": "Guardians of the Galaxy Vol. 2",
            "Released": "05 May 2017",
            "imdbID": "tt3896198",
            "Type": "movie",
        }
    )

    assert title.released_at is not None
    assert title.released_at.isoformat() == "2017-05-05T00:00:00"


def test_parse_season_episode_release_dates():
    season = OMDbSeason.model_validate(
        {
            "Title": "Example",
            "Season": "2",
            "Episodes": [
                {
                    "Title": "Pilot",
                    "Episode": "0",
                    "Released": "2025-01-01",
                    "imdbID": "tt0000000",
                },
                {
                    "Title": "One",
                    "Episode": "1",
                    "Released": "2026-08-01",
                    "imdbID": "tt0000001",
                },
                {
                    "Title": "Two",
                    "Episode": "2",
                    "Released": "N/A",
                    "imdbID": "tt0000002",
                },
            ],
        }
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


def test_api_error_returns_none():
    api = OMDbAPI(api_key="test-key")
    response = Mock()
    response.ok = True
    response.json.return_value = {"Response": "False", "Error": "Invalid IMDb ID."}
    api.session.get = Mock(return_value=response)

    assert api.get_title("invalid") is None
