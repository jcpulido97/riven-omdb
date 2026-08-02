from program.utils.torrent import extract_infohash


def test_extract_infohash_from_magnet_uri():
    assert (
        extract_infohash("magnet:?xt=urn:btih:a597664fa90231296b701882f018240c8606529f")
        == "a597664fa90231296b701882f018240c8606529f"
    )


def test_extract_infohash_from_peerflix_url():
    url = (
        "https://addon.peerflix.mov/realdebrid/"
        "RCGHJYBKTSXGZOWCROSBZAP5RMPKOZPU5X2JKSWH4HZT2YPQDI4Q/"
        "a597664fa90231296b701882f018240c8606529f/null/0/"
        "El%20arma%20del%20engano.mkv"
    )

    assert extract_infohash(url) == "a597664fa90231296b701882f018240c8606529f"


def test_unrelated_peerflix_token_is_not_treated_as_infohash():
    assert (
        extract_infohash(
            "https://addon.peerflix.mov/realdebrid/"
            "RCGHJYBKTSXGZOWCROSBZAP5RMPKOZPU5X2JKSWH4HZT2YPQDI4Q/null"
        )
        is None
    )
