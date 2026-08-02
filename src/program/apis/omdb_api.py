"""OMDb implementation of Riven's metadata-provider contract."""

import os
from datetime import datetime
from typing import Any

from cachetools import TTLCache
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from requests import RequestException

from program.metadata import normalize_imdb_id
from program.metadata.models import EpisodeMetadata, SeasonMetadata, TitleMetadata
from program.utils.request import SmartSession


class _OMDbTitleResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, alias="Title")
    released: str | None = Field(default=None, alias="Released")
    imdb_id: str | None = Field(default=None, alias="imdbID")
    media_type: str | None = Field(default=None, alias="Type")


class _OMDbEpisodeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, alias="Title")
    number: int = Field(alias="Episode")
    released: str | None = Field(default=None, alias="Released")
    imdb_id: str | None = Field(default=None, alias="imdbID")


class _OMDbSeasonResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, alias="Title")
    season: int = Field(alias="Season")
    episodes: list[_OMDbEpisodeResponse] = Field(default_factory=list, alias="Episodes")


class OMDbAPI:
    """OMDb metadata provider for titles, seasons, and episodes."""

    name = "omdb"
    BASE_URL = "https://www.omdbapi.com"
    API_KEY = os.environ.get("OMDB_API_KEY", "")

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or self.API_KEY
        self._title_cache = TTLCache[str, TitleMetadata | None](maxsize=4096, ttl=86400)
        self._season_cache = TTLCache[tuple[str, int], SeasonMetadata | None](
            maxsize=4096, ttl=21600
        )
        self.session = SmartSession(
            base_url=self.BASE_URL,
            rate_limits={"www.omdbapi.com": {"rate": 4, "capacity": 4}},
            retries=2,
            backoff_factor=0.3,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, **params: str | int) -> dict[str, Any] | None:
        """Make an OMDb request, always including the configured API key."""

        if not self.is_configured:
            return None

        try:
            response = self.session.get("/", params={"apikey": self.api_key, **params})

            if not response.ok:
                logger.debug(f"OMDb request failed with HTTP {response.status_code}")
                return None

            data = response.json()

            if data.get("Response") == "False":
                logger.debug(
                    f"OMDb request failed: {data.get('Error', 'unknown error')}"
                )
                return None

            return data
        except (RequestException, ValueError, TypeError) as error:
            logger.debug(f"OMDb request failed: {error}")
            return None

    def get_title(self, imdb_id: str | None) -> TitleMetadata | None:
        imdb_id = self.normalize_imdb_id(imdb_id)

        if imdb_id is None:
            return None

        if imdb_id in self._title_cache:
            return self._title_cache[imdb_id]

        data = self._get(i=imdb_id, plot="short", r="json")

        try:
            response = _OMDbTitleResponse.model_validate(data) if data else None
            result = (
                TitleMetadata(
                    title=response.title,
                    released_at=self.parse_release_date(response.released),
                    imdb_id=response.imdb_id,
                    media_type=response.media_type,
                )
                if response
                else None
            )
        except ValidationError as error:
            logger.debug(f"Invalid OMDb title response for {imdb_id}: {error}")
            result = None

        self._title_cache[imdb_id] = result
        return result

    def get_season(
        self, imdb_id: str | None, season_number: int
    ) -> SeasonMetadata | None:
        imdb_id = self.normalize_imdb_id(imdb_id)

        if imdb_id is None:
            return None

        cache_key = (imdb_id, season_number)

        if cache_key in self._season_cache:
            return self._season_cache[cache_key]

        data = self._get(i=imdb_id, Season=season_number, r="json")

        try:
            response = _OMDbSeasonResponse.model_validate(data) if data else None
            result = (
                SeasonMetadata(
                    number=response.season,
                    title=response.title,
                    episodes=[
                        EpisodeMetadata(
                            number=episode.number,
                            title=episode.title,
                            released_at=self.parse_release_date(episode.released),
                            imdb_id=episode.imdb_id,
                        )
                        for episode in response.episodes
                    ],
                )
                if response
                else None
            )
        except ValidationError as error:
            logger.debug(
                f"Invalid OMDb season response for {imdb_id} S{season_number}: {error}"
            )
            result = None

        self._season_cache[cache_key] = result
        return result

    @staticmethod
    def normalize_imdb_id(value: str | None) -> str | None:
        """Return a canonical IMDb ID or None when the value is invalid."""

        imdb_id = normalize_imdb_id(value)

        if value and imdb_id is None:
            logger.debug(f"Invalid IMDb ID for OMDb lookup: {value!r}")

        return imdb_id

    @staticmethod
    def parse_release_date(value: str | None) -> datetime | None:
        if not value or value == "N/A":
            return None

        for date_format in ("%d %b %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, date_format)  # noqa: DTZ007
            except ValueError:
                continue

        return None
