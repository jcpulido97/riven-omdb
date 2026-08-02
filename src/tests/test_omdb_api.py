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
    api.session.get = Mock()

    assert api.get_title("tt0000001") is None
    api.session.get.assert_not_called()


def test_api_key_is_read_when_provider_is_created(monkeypatch):
    monkeypatch.setenv("OMDB_API_KEY", " runtime-key ")

    api = OMDbAPI()

    assert api.api_key == "runtime-key"
    assert api.is_configured


def test_get_season_parses_episode_release_dates():
    api = OMDbAPI(api_key="test-key")
    response = Mock()
    response.ok = True
    response.json.return_value = {
        "Title": "Example Show",
        "Season": "2",
        "Episodes": [
            {
                "Title": "Future Episode",
                "Released": "09 Aug 2026",
                "Episode": "1",
                "imdbID": "tt0000002",
            },
            {
                "Title": "Unknown Episode",
                "Released": "N/A",
                "Episode": "2",
                "imdbID": "tt0000003",
            },
        ],
        "Response": "True",
    }
    api.session.get = Mock(return_value=response)

    season = api.get_season("tt0000001", 2)

    assert season is not None
    assert season.number == 2
    assert season.episodes[0].released_at is not None
    assert season.episodes[0].released_at.isoformat() == "2026-08-09T00:00:00"
    assert season.episodes[1].released_at is None
    api.session.get.assert_called_once_with(
        "/",
        params={
            "apikey": "test-key",
            "i": "tt0000001",
            "Season": 2,
            "r": "json",
        },
    )


def test_transient_title_failure_is_not_cached():
    api = OMDbAPI(api_key="test-key")
    failed = Mock(ok=False, status_code=503)
    succeeded = Mock(ok=True)
    succeeded.json.return_value = {
        "Title": "Recovered",
        "Released": "01 Jan 2026",
        "imdbID": "tt0000001",
        "Type": "movie",
        "Response": "True",
    }
    api.session.get = Mock(side_effect=[failed, succeeded])

    assert api.get_title("tt0000001") is None
    assert api.get_title("tt0000001") is not None
    assert api.session.get.call_count == 2


def test_non_object_json_response_is_ignored_and_retried():
    api = OMDbAPI(api_key="test-key")
    response = Mock(ok=True)
    response.json.return_value = []
    api.session.get = Mock(return_value=response)

    assert api.get_title("tt0000001") is None
    assert api.get_title("tt0000001") is None
    assert api.session.get.call_count == 2


def test_negative_season_does_not_make_request():
    api = OMDbAPI(api_key="test-key")
    api.session.get = Mock()

    assert api.get_season("tt0000001", -1) is None
    api.session.get.assert_not_called()
