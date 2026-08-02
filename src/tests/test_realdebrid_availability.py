from unittest.mock import Mock

from program.services.downloaders.models import TorrentInfo
from program.services.downloaders.realdebrid import RealDebridDownloader

INFOHASH = "a597664fa90231296b701882f018240c8606529f"
TORRENT_ID = "RD-torrent-id"
VIDEO_FILE = {
    1: {
        "path": "/El arma del engano.mkv",
        "filename": "El arma del engano.mkv",
        "bytes": 1_000_000_000,
        "selected": 1,
    }
}


def _torrent_info(status: str, files=None) -> TorrentInfo:
    return TorrentInfo(
        id=TORRENT_ID,
        name="El arma del engano",
        status=status,
        infohash=INFOHASH,
        files=files or {},
    )


def _downloader(*torrent_infos: TorrentInfo) -> RealDebridDownloader:
    downloader = RealDebridDownloader.__new__(RealDebridDownloader)
    downloader.get_torrent_info = Mock(side_effect=torrent_infos)
    downloader.select_files = Mock()
    return downloader


def test_cached_torrent_waits_for_selection_to_take_effect(mocker):
    sleep = mocker.patch("program.services.downloaders.realdebrid.time.sleep")
    downloader = _downloader(
        _torrent_info("waiting_files_selection", VIDEO_FILE),
        _torrent_info("waiting_files_selection", VIDEO_FILE),
        _torrent_info("downloaded", VIDEO_FILE),
    )

    container = downloader._process_torrent(TORRENT_ID, INFOHASH, "movie")

    assert container is not None
    assert container.cached
    assert container.file_ids == [1]
    downloader.select_files.assert_called_once_with(TORRENT_ID, [1])
    assert sleep.call_count == 2


def test_cached_torrent_waits_for_magnet_conversion(mocker):
    sleep = mocker.patch("program.services.downloaders.realdebrid.time.sleep")
    downloader = _downloader(
        _torrent_info("magnet_conversion"),
        _torrent_info("waiting_files_selection", VIDEO_FILE),
        _torrent_info("downloaded", VIDEO_FILE),
    )

    container = downloader._process_torrent(TORRENT_ID, INFOHASH, "movie")

    assert container is not None
    assert container.cached
    downloader.select_files.assert_called_once_with(TORRENT_ID, [1])
    assert sleep.call_count == 2


def test_uncached_torrent_still_returns_immediately(mocker):
    sleep = mocker.patch("program.services.downloaders.realdebrid.time.sleep")
    downloader = _downloader(_torrent_info("downloading", VIDEO_FILE))

    container = downloader._process_torrent(TORRENT_ID, INFOHASH, "movie")

    assert container is None
    downloader.select_files.assert_not_called()
    sleep.assert_not_called()
