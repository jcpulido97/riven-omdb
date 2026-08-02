from unittest.mock import Mock

import pytest
from kink import di

from program.apis.omdb_api import OMDbAPI
from program.media.item import MediaItem, Movie, Show
from program.media.state import States
from program.metadata import (
    MetadataLookupError,
    MetadataProviderError,
    MetadataService,
)
from program.services.indexers.omdb import OMDbIndexer
from program.state_transition import process_event


def _response(data: dict, *, ok: bool = True, status_code: int = 200) -> Mock:
    response = Mock(ok=ok, status_code=status_code)
    response.json.return_value = data
    return response


def test_api_key_is_read_at_provider_creation(monkeypatch):
    monkeypatch.setenv("OMDB_API_KEY", " runtime-key ")

    assert OMDbAPI().api_key == "runtime-key"


def test_movie_request_maps_release_metadata_and_api_key():
    api = OMDbAPI(api_key="test-key")
    api.session.get = Mock(
        return_value=_response(
            {
                "Title": "Operation Mincemeat",
                "Year": "2021",
                "Released": "11 May 2022",
                "Genre": "Drama, War",
                "Country": "United Kingdom, United States",
                "Language": "English",
                "imdbID": "tt1879016",
                "Type": "movie",
                "Response": "True",
            }
        )
    )

    title = api.get_title(" TT1879016 ")

    assert title is not None
    assert title.released_at.isoformat() == "2022-05-11T00:00:00"
    assert title.genres == ["drama", "war"]
    api.session.get.assert_called_once_with(
        "https://www.omdbapi.com/",
        params={
            "apikey": "test-key",
            "i": "tt1879016",
            "plot": "short",
            "r": "json",
        },
        timeout=30,
    )


def test_series_indexer_builds_stable_show_season_and_episode_ids():
    api = OMDbAPI(api_key="test-key")
    api.session.get = Mock(
        side_effect=[
            _response(
                {
                    "Title": "Example Show",
                    "Year": "2025–",
                    "Released": "01 Jan 2025",
                    "Genre": "Drama",
                    "Country": "United States",
                    "Language": "English",
                    "imdbID": "tt1234567",
                    "Type": "series",
                    "totalSeasons": "1",
                    "Response": "True",
                }
            ),
            _response(
                {
                    "Title": "Example Show",
                    "Season": "1",
                    "Episodes": [
                        {
                            "Title": "Released",
                            "Released": "01 Jan 2025",
                            "Episode": "1",
                            "imdbID": "tt1234568",
                        },
                        {
                            "Title": "Future",
                            "Released": "01 Jan 2099",
                            "Episode": "2",
                            "imdbID": "tt1234569",
                        },
                    ],
                    "Response": "True",
                }
            ),
        ]
    )
    di[MetadataService] = MetadataService([api])
    indexer = OMDbIndexer()

    show = next(indexer.run(MediaItem({"imdb_id": "tt1234567"})))

    assert isinstance(show, Show)
    assert show.id == "show_tt1234567"
    assert show.seasons[0].id == "season_tt1234567_1"
    assert [episode.id for episode in show.seasons[0].episodes] == [
        "episode_tt1234568",
        "episode_tt1234569",
    ]
    assert show.seasons[0].episodes[0].state == States.Indexed
    assert show.seasons[0].episodes[1].state == States.Unreleased


def test_movie_release_date_drives_release_state():
    api = OMDbAPI(api_key="test-key")
    api.session.get = Mock(
        return_value=_response(
            {
                "Title": "Future Movie",
                "Year": "2099",
                "Released": "01 Jan 2099",
                "imdbID": "tt7654321",
                "Type": "movie",
                "Response": "True",
            }
        )
    )
    di[MetadataService] = MetadataService([api])

    movie = next(OMDbIndexer().run(MediaItem({"imdb_id": "tt7654321"})))

    assert isinstance(movie, Movie)
    assert movie.id == "movie_tt7654321"
    assert movie.state == States.Unreleased


def test_transient_failure_is_not_cached():
    api = OMDbAPI(api_key="test-key")
    api.session.get = Mock(
        side_effect=[
            _response({}, ok=False, status_code=503),
            _response(
                {
                    "Title": "Recovered",
                    "Released": "01 Jan 2020",
                    "imdbID": "tt0000001",
                    "Type": "movie",
                    "Response": "True",
                }
            ),
        ]
    )

    with pytest.raises(MetadataProviderError, match="omdb: HTTP 503"):
        api.get_title("tt0000001")
    assert api.get_title("tt0000001") is not None
    assert api.session.get.call_count == 2


def test_indexer_retries_after_transient_provider_failure():
    api = OMDbAPI(api_key="test-key")
    api.session.get = Mock(
        side_effect=[
            _response({}, ok=False, status_code=503),
            _response(
                {
                    "Title": "Recovered",
                    "Released": "01 Jan 2020",
                    "imdbID": "tt0000001",
                    "Type": "movie",
                    "Response": "True",
                }
            ),
        ]
    )
    di[MetadataService] = MetadataService([api])
    indexer = OMDbIndexer()
    item = MediaItem({"imdb_id": "tt0000001"})

    with pytest.raises(MetadataLookupError, match="omdb: HTTP 503"):
        list(indexer.run(item))
    assert isinstance(next(indexer.run(item)), Movie)


def test_omdb_quota_error_preserves_message_and_maps_to_http_429():
    api = OMDbAPI(api_key="test-key")
    api.session.get = Mock(
        return_value=_response(
            {"Response": "False", "Error": "Request limit reached!"},
            ok=False,
            status_code=401,
        )
    )
    service = MetadataService([api])

    with pytest.raises(MetadataLookupError) as captured:
        service.get_title("tt1879016")

    assert str(captured.value) == "omdb: Request limit reached!"
    assert captured.value.http_status == 429
    assert captured.value.errors[0].upstream_status == 401


def test_missing_key_skips_requests():
    api = OMDbAPI(api_key="")
    api.session.get = Mock()

    assert api.get_title("tt0000001") is None
    api.session.get.assert_not_called()


def test_new_content_uses_omdb_indexer_by_default():
    item = MediaItem({"imdb_id": "tt0000001"})

    next_service, submitted_items = process_event(None, content_item=item)

    assert next_service is OMDbIndexer
    assert submitted_items == [item]
