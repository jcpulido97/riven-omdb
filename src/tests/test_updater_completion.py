from unittest.mock import Mock

from program.media.item import Movie
from program.media.state import States
from program.services.updaters import Updater


def _movie() -> Movie:
    movie = Movie(
        {
            "id": "movie_tt1879016",
            "imdb_id": "tt1879016",
            "title": "Operation Mincemeat",
            "type": "movie",
        }
    )
    movie.symlinked = True
    movie.update_folder = "/library/movies/Operation Mincemeat"
    return movie


def _updater(service) -> Updater:
    updater = Updater.__new__(Updater)
    updater.initialized = True
    updater.services = {type(service): service}
    return updater


def test_empty_media_server_update_still_completes_item():
    service = Mock(initialized=True)
    service.run.return_value = iter(())
    movie = _movie()

    result = list(_updater(service).run(movie))

    assert result == [movie]
    assert movie.update_folder == "updated"
    assert movie.state == States.Completed


def test_successful_media_server_update_completes_item():
    service = Mock(initialized=True)
    movie = _movie()
    service.run.return_value = iter((movie,))

    result = list(_updater(service).run(movie))

    assert result == [movie]
    assert movie.update_folder == "updated"
    assert movie.state == States.Completed


def test_media_server_exception_does_not_block_completion():
    service = Mock(initialized=True)
    service.run.side_effect = RuntimeError("refresh failed")
    movie = _movie()

    result = list(_updater(service).run(movie))

    assert result == [movie]
    assert movie.update_folder == "updated"
    assert movie.state == States.Completed


def test_no_configured_media_server_keeps_optional_updater_behavior():
    service = Mock(initialized=False)
    movie = _movie()

    result = list(_updater(service).run(movie))

    assert result == [movie]
    assert movie.state == States.Completed
