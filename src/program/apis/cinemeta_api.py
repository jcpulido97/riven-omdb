from typing import NamedTuple

from cachetools import TTLCache
from loguru import logger
from requests import RequestException

from program.metadata import normalize_imdb_id
from program.utils.request import create_service_session, get_rate_limit_params


class ExternalIDs(NamedTuple):
    tmdb_id: str | None = None
    tvdb_id: str | None = None


class CinemetaAPI:
    """Resolve frontend-required external IDs from an IMDb ID."""

    BASE_URL = "https://v3-cinemeta.strem.io/meta"

    def __init__(self):
        self._cache = TTLCache(maxsize=4096, ttl=86400)
        self.session = create_service_session(
            rate_limit_params=get_rate_limit_params(max_calls=4, period=1)
        )

    def get_external_ids(
        self, imdb_id: str | None, media_type: str | None
    ) -> ExternalIDs:
        imdb_id = normalize_imdb_id(imdb_id)
        cinemeta_type = "series" if media_type in ("series", "show") else "movie"
        if imdb_id is None:
            return ExternalIDs()

        cache_key = (imdb_id, cinemeta_type)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            response = self.session.get(
                f"{self.BASE_URL}/{cinemeta_type}/{imdb_id}.json", timeout=30
            )
            response.raise_for_status()
            metadata = response.json().get("meta", {})
            result = ExternalIDs(
                tmdb_id=self._string_id(metadata.get("moviedb_id")),
                tvdb_id=self._string_id(metadata.get("tvdb_id")),
            )
        except (RequestException, AttributeError, TypeError, ValueError) as error:
            logger.warning(
                f"Failed to resolve external IDs for {imdb_id}: {error}"
            )
            result = ExternalIDs()

        if result.tmdb_id or result.tvdb_id:
            self._cache[cache_key] = result
        return result

    @staticmethod
    def _string_id(value) -> str | None:
        if value in (None, ""):
            return None
        return str(value)
