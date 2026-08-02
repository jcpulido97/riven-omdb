from program.utils.torrent import extract_infohash

INFOHASH = "a597664fa90231296b701882f018240c8606529f"


def test_extract_infohash_from_magnet_uri():
    assert extract_infohash(f"magnet:?xt=urn:btih:{INFOHASH}") == INFOHASH


def test_extract_infohash_from_peerflix_realdebrid_url():
    url = (
        "https://addon.peerflix.mov/realdebrid/provider-token/"
        f"{INFOHASH}/null/0/El%20arma%20del%20enga%C3%B1o.mkv"
    )
    assert extract_infohash(url) == INFOHASH


def test_provider_token_is_not_treated_as_infohash():
    url = (
        "https://addon.peerflix.mov/realdebrid/"
        "RCGHJYBKTSXGZOWCROSBZAP5RMPKOZPU5X2JKSWH4HZT2YPQDI4Q/null/0/file.mkv"
    )
    assert extract_infohash(url) is None
