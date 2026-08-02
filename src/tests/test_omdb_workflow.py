from unittest.mock import Mock

from kink import di

import program.apis as api_bootstrap
from program.apis.omdb_api import OMDbAPI
from program.media.item import Movie
from program.media.state import States
from program.metadata import MetadataService


def _title_response(released: str) -> Mock:
    response = Mock(ok=True)
    response.json.return_value = {
        "Title": "Workflow Movie",
        "Released": released,
        "imdbID": "tt1879016",
        "Type": "movie",
        "Response": "True",
    }
    return response


def test_bootstrap_registers_configured_omdb_as_default_provider(monkeypatch):
    monkeypatch.setenv("OMDB_API_KEY", "runtime-key")

    api_bootstrap.__setup_metadata()

    metadata = di[MetadataService]
    assert [provider.name for provider in metadata.providers] == ["omdb"]
    assert [provider.name for provider in metadata.configured_providers] == ["omdb"]
    assert di[OMDbAPI] is metadata.providers[0]


def test_omdb_release_date_drives_movie_release_state():
    omdb = OMDbAPI(api_key="test-key")
    omdb.session.get = Mock(
        side_effect=[_title_response("11 May 2022"), _title_response("01 Jan 2099")]
    )
    metadata = MetadataService([omdb])

    released = metadata.get_title("tt1879016")
    assert released is not None
    released_movie = Movie(
        {
            "title": released.title,
            "type": "movie",
            "imdb_id": released.imdb_id,
            "aired_at": released.released_at,
        }
    )

    # Use a second provider instance because successful title responses are cached.
    future_omdb = OMDbAPI(api_key="test-key")
    future_omdb.session.get = Mock(return_value=_title_response("01 Jan 2099"))
    future = MetadataService([future_omdb]).get_title("tt1879016")
    assert future is not None
    future_movie = Movie(
        {
            "title": future.title,
            "type": "movie",
            "imdb_id": future.imdb_id,
            "aired_at": future.released_at,
        }
    )

    assert released_movie.state == States.Indexed
    assert future_movie.state == States.Unreleased
