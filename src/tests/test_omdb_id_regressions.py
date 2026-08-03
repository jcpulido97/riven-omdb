import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from program.apis.cinemeta_api import ExternalIDs
from program.db.db import db
from program.media.item import MediaItem, Movie, Season, Show
from program.program import Program
from program.services.indexers.omdb import OMDbIndexer
from routers.secure.items import get_item

pytestmark = pytest.mark.usefixtures("isolated_database")


@pytest.fixture
def isolated_database(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    db.Model.metadata.create_all(engine)
    monkeypatch.setattr(db, "Session", lambda: Session(engine))
    yield engine
    db.Model.metadata.drop_all(engine)
    engine.dispose()


def _stored_movie(session: Session, *, tmdb_id: str | None = "661231") -> Movie:
    movie = Movie(
        {
            "id": "movie_tt1879016",
            "imdb_id": "tt1879016",
            "tmdb_id": tmdb_id,
            "title": "Operation Mincemeat",
            "aired_at": datetime(2022, 5, 11),
            "type": "movie",
        }
    )
    movie.store_state()
    session.add(movie)
    session.commit()
    return movie


@pytest.mark.parametrize("lookup_id", ["movie_tt1879016", "tt1879016", "661231"])
def test_item_detail_accepts_internal_imdb_and_tmdb_ids(
    lookup_id,
):
    with db.Session() as session:
        _stored_movie(session)

    result = asyncio.run(get_item(None, lookup_id, media_type="movie"))

    assert result["id"] == "movie_tt1879016"
    assert result["imdb_id"] == "tt1879016"
    assert result["tmdb_id"] == "661231"


def test_null_navigation_id_does_not_match_an_item():
    with db.Session() as session:
        _stored_movie(session)

    with pytest.raises(HTTPException) as captured:
        asyncio.run(get_item(None, "null", media_type="movie"))

    assert captured.value.status_code == 404


def test_api_serializes_frontend_type_and_correct_parent_ids():
    show = Show(
        {
            "id": "show_tt0944947",
            "imdb_id": "tt0944947",
            "tmdb_id": "1399",
            "tvdb_id": "121361",
            "title": "Game of Thrones",
            "type": "show",
        }
    )
    season = Season(
        {"id": "season_tt0944947_1", "number": 1, "type": "season"}
    )
    show.add_season(season)
    show.store_state()

    serialized = season.to_dict()

    assert serialized["type"] == "season"
    assert serialized["parent_ids"] == {
        "trakt_id": None,
        "imdb_id": "tt0944947",
        "tvdb_id": "121361",
        "tmdb_id": "1399",
    }
    assert serialized["poster_path"] == (
        "https://images.metahub.space/poster/small/tt0944947/img"
    )


def test_movie_api_serializes_poster_for_existing_database_rows():
    with db.Session() as session:
        _stored_movie(session)

    result = asyncio.run(get_item(None, "tt1879016", media_type="movie"))

    assert result["poster_path"] == (
        "https://images.metahub.space/poster/small/tt1879016/img"
    )


def test_background_backfill_repairs_existing_omdb_item():
    with db.Session() as session:
        _stored_movie(session, tmdb_id=None)

    resolver = SimpleNamespace(
        get_external_ids=lambda _imdb_id, _media_type: ExternalIDs(
            tmdb_id="661231"
        )
    )
    program = Program.__new__(Program)
    program.services = {
        OMDbIndexer: SimpleNamespace(identifiers=resolver),
    }

    program._backfill_external_ids()

    with db.Session() as session:
        movie = session.execute(
            select(MediaItem).where(MediaItem.id == "movie_tt1879016")
        ).unique().scalar_one()
        assert movie.tmdb_id == "661231"


def test_background_backfill_does_not_change_processing_state():
    with db.Session() as session:
        movie = _stored_movie(session, tmdb_id=None)
        original_state = movie.last_state

    resolver = SimpleNamespace(
        get_external_ids=lambda _imdb_id, _media_type: ExternalIDs(
            tmdb_id="661231"
        )
    )
    program = Program.__new__(Program)
    program.services = {
        OMDbIndexer: SimpleNamespace(identifiers=resolver),
    }

    program._backfill_external_ids()

    with db.Session() as session:
        movie = session.get(MediaItem, "movie_tt1879016")
        assert movie.last_state == original_state
